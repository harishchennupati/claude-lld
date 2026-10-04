"""Part 3 and the end: where it runs, how it scales, what breaks, consistency, latency and cost,
security, how a change goes out, what to watch, the recap and the technical round."""
from rag_v5_text import band, calc, fu, h2, how, qa, say, table, tx, ul


def body(fig):
    B = []
    B.append(band('Part 3', 'Running it: what interviewers ask after the design'))

    # ---------------------------------------------------------------- where it runs
    B.append(h2('s-run', 'Where it runs: three zones, one region, a cell per company'))
    B.append(tx('''A <b>region</b> is one place where a cloud platform has data centres, such as Frankfurt.
        Its <b>zones</b> are separate buildings about a millisecond apart. A company's cell runs across
        three zones of one region, inside the area the company chose. Backups go to a second region
        in the same area. Prompts go only to model endpoints inside the area, so the company's text
        never leaves it, not even for the fallback provider.'''))
    B.append(fig(12, '''Top: dashed boxes are cells. Bottom: one question arriving in zone A, which holds
        every primary. A question arriving in B or C reads the primaries from there.'''))
    B.append(ul(
        '''<b>Stateless parts</b> (orchestrators, GPU pool, ingest workers) run in all three zones
        behind a load balancer. A dead zone loses a third of the capacity and nothing else.''',
        '''<b>The metadata database</b> has one primary and a copy in each other zone. A commit waits
        until one copy has it, because the identity provider sends each change once. A removal lost
        with a dead primary would let a removed employee read on.''',
        '''<b>The search index</b> keeps one copy of each shard in each zone. Any copy answers
        reads.''',
        '''<b>Kafka</b> keeps three copies of every message, one per zone.''',
        '''<b>One region is enough at 99.9%.</b> A second live cell would double the cost to save a
        few hours in a rare regional outage. A regional outage is a restore, not a failover.'''))
    B.append(say('''One cell per large company, in its own area, across three zones. Stateless parts
        everywhere, one database primary, three copies of every shard and every message.'''))

    # ---------------------------------------------------------------- scaling
    B.append(h2('s-scale', 'How each part scales, and what breaks first'))
    B.append(tx('''Interviewers ask "what happens at 10 times the load?" Answer part by part. Each part
        scales in its own way and has its own limit.'''))
    B.append(table(['part', 'how it scales', 'its limit'], [
        ['Orchestrators', '''Stateless. Add servers behind the load balancer. Each holds hundreds of
         open streams, because they mostly wait on the provider.''', '''Never the bottleneck. The
         provider's rate limit is.'''],
        ['Model provider', '''Negotiate a higher token limit. Send simple questions to a smaller,
         cheaper model. Split traffic across two providers.''', '''The token limit, about 300,000
         tokens a second at today's peak. This is the first wall at 10×.'''],
        ['Search index', '''Add copies for more reads. Add shards for more data: build the new index
         beside the old one and switch with one row, because resharding in place blocks writes.''',
         '''RAM. At 10× the vectors are about 1.2 TB, so 40 shards, or one bit a number in RAM
         with rescoring from SSD.'''],
        ['Metadata database', '''One primary, read copies in each zone. The final check is one small
         query a question, about 50 a second, which is nothing for Postgres.''', '''Write bursts: a
         folder shared with a new group rewrites many rows. Batch them in transactions of a
         thousand.'''],
        ['Ingest queue and workers', '''Kafka partitions by document id. Add workers up to the
         partition count. Backfills go on a separate topic, so a new company never delays anyone's
         edits.''', '''The sources' API quotas, about 30 documents a second each. We cannot read
         faster than the source allows.'''],
        ['GPU pool', '''Autoscale on queue depth. Under pressure, rerank 50 candidates instead of
         100.''', '''GPU supply and cost. Reranking is the biggest GPU user.'''],
        ['Redis', '''Tiny data: principal lists and token buckets. One cluster per cell.''',
         '''None in practice. If it dies, everything falls back to the database.'''],
    ]))
    B.append(tx('''<b>Backpressure.</b> When a part is slow, the parts before it must not pile up work.
        Each employee may ask 60 questions an hour. A question whose provider bucket is empty waits
        up to 2 seconds, then goes to the fallback. Ingest workers pull from Kafka at their own pace.
        So a burst of edits waits in the queue instead of overloading the sources or the index.'''))
    B.append(say('''At 10×, the provider's token limit breaks first, then the index's RAM, then the GPUs.
        The sources' quotas cap how fast a new company loads. Everything of ours is stateless or
        sharded, so the fix is more machines, except the index, which needs a new build.'''))
    B.append(fu(
        ('A new company connects 10 million documents on Monday. When can its employees ask?',
         '''After about a day, because the most recently edited documents load first. At about 30
         documents a second from the source, all 10 million take about 4 days. Embedding them takes
         only about 2 hours.'''),
        ('Why not one giant index for all companies, with more shards?',
         '''Push 12. A filter bug would cross companies, one busy company would slow the rest, and an
         EU company's text would sit outside the EU.''')))

    # ---------------------------------------------------------------- when it breaks
    B.append(h2('s-break', 'When something breaks: the model provider first'))
    B.append(tx('''The provider fails most often, so the model router's <b>circuit breaker</b> is the
        first story to tell. Its states are named after an electric circuit. <b>Closed:</b> calls
        pass. <b>Open:</b> calls go to the fallback. <b>Half open:</b> a few trial calls test the
        provider.'''))
    B.append(fig(13, 'A 529 is the provider\'s "overloaded" error.'))
    B.append(table(['what fails', 'what employees see meanwhile', 'back in'], [
        ['the model provider', '''Nothing. The breaker opens after half of 20 calls fail in 10
         seconds, and the fallback provider answers.''', 'when it recovers'],
        ['both providers', '''A search-only answer: the 8 checked chunks as links. Never an
         error.''', 'when one recovers'],
        ['the GPU pool', '''No embeddings: keyword search only. No reranker: fused order, no
         abstaining. No checker: citations marked "not checked".''', 'minutes'],
        ['one index node', '''Nothing. The two other copies answer while a peer copies the shard
         back.''', 'about 30 min'],
        ['the database primary', '''"I can't check permissions right now" while a copy is
         promoted.''', 'about 30 s'],
        ['Redis', '''Principal lists come from the database. No answer cache. Each orchestrator
         counts its own share of each provider limit.''', 'seconds'],
        ['a source, or the identity provider', '''That source's edits wait and an alarm fires.
         Signed-in employees keep asking.''', 'when it recovers'],
        ['a whole zone', '''Nothing, if the database primary was elsewhere. Otherwise 30 seconds of
         refused final checks.''', 'minutes'],
    ]))
    B.append(tx('''<b>Backups and recovery.</b> <b>RPO</b> is the data a failure loses. <b>RTO</b> is the
        time until service returns. For a lost machine or zone, RPO is zero, because the database and
        Kafka confirm a write only once another zone has it. For a lost region or a corrupted index:'''))
    B.append(ul(
        '''<b>Metadata database:</b> nightly backup plus the write-ahead log, restorable to any
        second. Then the connectors re-read every change since, and the daily sweep runs at once.
        RTO about an hour.''',
        '''<b>Search index:</b> rebuilt from the database and the stored vectors in about 3 hours. No
        GPU needed. Three copies protect against a lost machine, not a bad change, which reaches all
        three. That is why every change builds a new index beside the old one.''',
        '''<b>Object storage:</b> versioned and copied to the second region. Nothing to restore.''',
        '''<b>Conversations:</b> same as the metadata database. Losing a day of history is
        acceptable. Losing a day of permissions is not.'''))
    B.append(say('''No first word in 3 seconds moves a question to the fallback. Half of 20 calls failing
        opens the breaker. Both providers down means search-only answers, never an error. RPO zero
        for a zone. A region is a restore of about an hour.'''))
    B.append(fu(
        ('One index node is slow, not down. What happens to every question?',
         '''Each question asks all 4 shards, so one slow copy would slow them all. A shard still
         searching after 80 ms is asked again on its copy in another zone, and the first answer
         wins.'''),
        ('How do you know the backup works?',
         '''Restore it into a test cell every month and run the golden set against it.''')))

    # ---------------------------------------------------------------- CAP
    B.append(h2('s-cap', 'Consistency: what a network split does'))
    B.append(tx('''In a <b>network partition</b>, two groups of machines cannot reach each other. The
        <b>CAP theorem</b> says each part must then choose. <b>Consistency</b> means every read sees
        the latest truth. <b>Availability</b> means every request is answered, perhaps from stale
        data.
        Ask of each part: if it is cut off, what does she see?'''))
    B.append(ul(
        '''<b>The final check</b> chooses consistency. A zone that cannot reach the database primary
        refuses. The load balancer moves its questions to a zone that can.''',
        '''<b>The search index</b> chooses availability. A cut-off copy answers from what it holds.
        That is safe, because the final check comes after it.''',
        '''<b>Redis</b> chooses availability. A stale principal list only affects recall.''',
        '''<b>Ingest and the identity sync</b> queue their changes in Kafka until the split heals.
        Nothing is lost, and nothing is applied out of order.''',
        '''<b>The conversation store</b> chooses availability. The question is answered as a first
        turn and saved later.'''))
    B.append(say('''In a split, the gate chooses consistency and everything before it chooses
        availability. The final check reads the primary, even from another zone, because it is the
        one step that must be exact.'''))

    # ---------------------------------------------------------------- ledgers
    B.append(h2('s-ledger', 'The latency budget and the cost'))
    B.append(tx('''Interviewers ask for these two ledgers, usually as "where would you cut?". First, the
        time to Asha's first word:'''))
    B.append(table(['step', 'takes', 'clock'], [
        ['save her turn, read her principals, embed and classify the question', 'about 20 ms', '20 ms'],
        ['vector and keyword searches on all 4 shards, side by side, then fusion', 'about 40 ms', '60 ms'],
        ['the reranker scores up to 100 candidates', 'about 90 ms', '150 ms'],
        ['the final check on 20 ids, then pack the prompt', 'about 5 ms', '155 ms'],
        ['the provider reads 6,000 tokens and writes its first word', 'about 700 ms', '0.9 s'],
        ['a follow-up adds the rewrite before the searches', '+ 400 ms', '1.3 s'],
    ], 'led'))
    B.append(tx('''Most of the second is the provider's. To reach half a second, the lever is a smaller,
        faster model for ordinary questions. Reranking 50 instead of 100 saves only about 50 ms.'''))
    B.append(tx('''Second, the cost. Three quarters of each answer is input tokens, so every lever is
        about fewer input tokens, or cheaper ones:'''))
    B.append(calc('''one answer     6,000 in × $3 per M = 1.8 ¢   +   400 out × $15 per M = 0.6 ¢   →  about 2.5 ¢
one day        500,000 answers × 2.5 ¢                                             →  about $12,000

<b>the levers</b>
  cache the 1,100 instruction tokens at the provider (a tenth of the price)   saves about 0.3 ¢ an answer, $1,500 a day
  8 chunks after the reranker, not 20                                         saves about $9,000 a day
  no model call when the best score is below 0.3                              a whole call per unanswerable question
  a small rewrite model, not the large one                                    saves about $1,000 a day
  cached first answers, about 1 in 10                                         saves about $500 a day, and those start in 0.2 s'''))
    B.append(tx('''<b>The answer cache</b> in Redis serves a first turn only when its prompt would repeat an
        earlier one exactly. That means the same question after rewriting, the same 8 chunks after the
        final check, and the same prompt version. That is safe without knowing who asked, because whoever reaches those 8 chunks
        has just passed the final check on all of them. Follow-ups carry the conversation, so they are
        never cached.'''))
    B.append(say('''The first word is mostly the provider's 0.7 seconds. The cost is three quarters input,
        so the levers are fewer input tokens and cached ones.'''))

    # ---------------------------------------------------------------- security
    B.append(h2('s-sec', 'Security and privacy'))
    B.append(tx('''Permissions are the big one, and Part 2 covered them. Interviewers also ask about the
        rest. Have one line for each:'''))
    B.append(ul(
        '''<b>Identity.</b> Sign-in is the company's single sign-on. Who she is comes from her
        session, never from the request. Her principals come from our records.''',
        '''<b>In transit and at rest.</b> TLS on every connection, including between our own
        services. Every store is encrypted at rest with a key per company, so leaving a company
        means deleting its key.''',
        '''<b>The provider.</b> A contract with zero retention: it keeps no prompts and trains on
        none. Prompts go only to endpoints inside the company's area.''',
        '''<b>Audit.</b> Every turn stores the ids of the chunks its prompt held. So "who saw this
        document through the assistant?" is one query.''',
        '''<b>Least privilege for us.</b> Our staff reach a company's data only through audited
        emergency access, which the company can see.''',
        '''<b>Over-shared documents.</b> The assistant turns a forgotten mistake into a one-line
        answer. So admins can exclude folders and sensitivity labels from indexing, and a weekly
        report lists widely shared documents that match sensitive terms.''',
        '''<b>Abuse.</b> 60 questions an hour per employee. A company has its own token bucket inside
        the cell's. The trace log is kept 30 days with personal details removed.''',
        '''<b>Injection.</b> Part 2: retrieved text is quoted data, the model has no tools, the page
        clicks only cited links.'''))
    B.append(say('''Permissions at the gate. A key per company. Zero retention at the provider. An audit trail of
        chunk ids. No tools for the model.'''))

    # ---------------------------------------------------------------- change
    B.append(h2('s-change', 'Quality: how a change goes out'))
    B.append(tx('''<b>The problem.</b> A new chunker cuts code blocks in the wrong place. It passed the
        golden set with better recall, because last month's questions hold few about code. Nothing
        errors. Answers about commands just get worse.'''))
    B.append(tx('<b>The solution</b> is three checks in a row, and one row to roll back:'))
    B.append(how(
        '''<b>The golden set, offline.</b> About 1,000 past questions, sampled monthly from the trace
        log, each labelled with the passage that answers it. Some have no answer, to test abstaining.
        Old and new versions answer it in pairs.''',
        '''<b>A shadow run,</b> for changes that need a new index. For two days, 5% of real questions
        are also answered on the new index, unseen, and compared.''',
        '''<b>A canary.</b> 5% of conversations for a day, compared with the other 95%. A signal that
        passes its limit rolls the change back automatically.'''))
    B.append(table(['signal', 'what it counts', 'fails when'], [
        ['recall at 8', 'golden questions where one of the 8 chunks sent holds the labelled passage',
         'offline: 2 points lower'],
        ['faithfulness', 'claim sentences that a larger grading model finds supported',
         'offline: 2 points lower'],
        ['abstain accuracy', 'answerable questions answered, unanswerable ones refused',
         'offline: 2 points lower'],
        ['thumbs-down', 'per 100 answers, canary against the other 95%, overall and per slice',
         'canary: 2 points higher for an hour'],
        ['first word, cost', 'the guard rails', 'canary: 300 ms slower, 15% dearer'],
    ]))
    B.append(tx('''<b>The hardest change is a new embedding model.</b> Two models' vectors cannot be
        compared. So a new index is built beside the old one from the parsed text in object storage,
        while every live change is written to both. After the shadow run and the canary, one row in
        the database switches the index and the model together. Both stay live for a week, so going
        back is the same one-row write. Models are pinned by exact version id, never "latest".'''))
    B.append(say('''Golden set, then shadow, then a 5% canary that rolls itself back. A new embedding
        model means a new index beside the old, switched with one row.'''))
    B.append(fu(
        ('Interviewers name MRR or nDCG. Why gate on recall at 8?',
         '''Those scores reward putting the right chunk nearer the top. The model reads all 8, so
         what matters is whether the right one got in.'''),
        ('A manager says yesterday\'s answer was wrong. How do you find which step failed?',
         '''Open the turn in the trace log. Was the rewritten question right? Was the right chunk
         among the 100 candidates, the reranker's 20, the 8 packed? What did the checker say? Each
         step points to its own fix, and the question joins the golden set.''')))

    # ---------------------------------------------------------------- watch
    B.append(h2('s-watch', 'What to watch'))
    B.append(tx('''Every turn writes one trace record with its candidates, scores, timings and tokens. The
        dashboards and alarms come from it:'''))
    B.append(table(['watch', 'page someone when'], [
        ['the first word, 95th percentile', 'above 2 seconds for 10 minutes'],
        ['the model router\'s breakers', 'a breaker opens'],
        ['questions refused by the final check', 'more than 1 in 1,000: the primary is slow or unreachable'],
        ['chunks dropped by the final check', 'more than 2%: the search side lags'],
        ['ingest lag, from edit to searchable', 'above 5 minutes for 15 minutes'],
        ['citations failing the check', 'half again above usual'],
        ['cost per answer', 'above 3 cents'],
        ['thumbs-down per 100 answers', 'up by 2 points for an hour'],
    ]))
    B.append(say('''Four numbers tell the health: time to first word, final-check refusals, ingest lag,
        and thumbs-down. The trace log explains any of them.'''))

    # ================================================================ End
    B.append(band('End', 'Remember it'))
    B.append(h2('s-recap', 'Remember it: the map, the numbers, and the 45 minutes'))
    B.append(tx('''<b>The map.</b> Read only the bold word, say the rest aloud, then check. Do it on day 1,
        3, 7 and 10.'''))
    mp = [
        ('what it is', 'a search engine whose results a model reads · exact gates, approximate middle'),
        ('the path', 'rewrite → embed → filtered keyword + vector search → fuse → rerank → final check → '
                     '8 chunks → stream → check citations'),
        ('gate 1', 'the final check: 20 chunks against the metadata database, where every change lands first'),
        ('gate 2', 'a citation may name only a chunk we sent'),
        ('ingest', 'webhook is a doorbell → read the change list → Kafka by document id → fetch '
                   'ticket → only changed chunks embedded'),
        ('permissions', 'groups and folders on the chunk, not people · filter early, check late'),
        ('freshness', 'latest fetch wins · a delete is one transaction, honoured at the gate that second'),
        ('follow-ups', 'rewrite to a standalone question · rolling summary · fixed prompt, instructions first'),
        ('not found', 'best reranker score below 0.3: no model call, say so'),
        ('injection', 'quoted text, no tools, only cited links clickable, output filter'),
        ('failure', '3 s to first word or fallback · breaker on half of 20 calls · both down → search-only'),
        ('scale', '10×: provider limit first, then index RAM, then GPUs'),
        ('change', 'golden set → shadow → 5% canary that rolls back · new embedder = new index beside'),
    ]
    B.append('<div class="map">' + ''.join(f'<p><b>{k}</b> {v}</p>' for k, v in mp) + '</div>')
    B.append(tx('<b>The numbers to carry into the room</b>, all rounded:'))
    card = [
        ('load', '500,000 a day · peak 50 a second'), ('chunks', '10 M docs × 10 = 100 M'),
        ('vectors', '1 KB each → 100 GB, 120 with the graph'), ('nodes', '4 shards × 3 copies = 12'),
        ('prompt', '6,000 in, 400 out'), ('tokens', '300,000 a second at peak'),
        ('cost', '2.5 ¢ an answer, $12,000 a day'), ('first word', '0.9 s · done in 7 s'),
        ('ours', '150 ms before the model'), ('funnel', '50 + 50 → 100 → 20 → 8'),
        ('chunk', '480 tokens, 50 overlap'), ('fusion', '1 / (60 + rank)'),
        ('abstain', 'best score below 0.3'), ('cite', 'checker 0.5 or more'),
        ('cache', 'principals 60 s'), ('fresh', 'edit 5 min, delete 1 min'),
        ('breaker', '3 s · half of 20 · probe 30 s'), ('checks', '1,000 golden · 5% canary a day'),
        ('available', '99.9% = 45 min a month'), ('GPUs', '12, 4 a zone'),
        ('servers', '6 orchestrators, 150 ingest workers'),
    ]
    B.append('<div class="card">' + ''.join(f'<p><b>{k}</b> {v}</p>' for k, v in card) + '</div>')
    B.append(tx('''<b>How to run the 45 minutes.</b> Interviews on this problem follow the same arc. Have
        the opening of each step ready:'''))
    plan = [
        ('0–5 min', '''<b>Requirements.</b> Read back the five jobs, ask about scale, and open with "This
         is a search engine whose results a model reads. The design is everything around the model,
         and two things in it must be exact."'''),
        ('5–10 min', '<b>The numbers:</b> 50 a second, 100 M chunks, 120 GB, 2.5 ¢ an answer.'),
        ('10–18 min', '''<b>Draw the picture</b> in three bands, parts in the order of the pushes, the
         two gates marked.'''),
        ('18–25 min', '''<b>One question through it</b>, with timings: approximate up to the reranker,
         exact at the final check, streamed and checked after the model.'''),
        ('25–40 min', '''<b>The deep dives they pick.</b> Permissions and freshness come up most. Have
         retrieval, follow-ups and citations ready. If they leave it to you, ask: "I can go deeper on
         permissions, freshness or answer quality. Which matters most to you?"'''),
        ('40–45 min', '<b>Running it:</b> the provider failing, 10× load, the cost, how a change goes out.'),
    ]
    B.append('<ol class="plan">' + ''.join(f'<li><b>{t}</b><span>{" ".join(s.split())}</span></li>'
                                           for t, s in plan) + '</ol>')

    # ---------------------------------------------------------------- technical round
    B.append(h2('s-round', 'The technical round: six questions interviewers push on'))
    B.append(qa('''A connector maps a restricted page as readable by all staff. The search filter and the
        final check both trust that row. What catches it?''',
        '''Neither can, so it is caught where permissions are written. Each connector ships with a test
        suite of documents whose readers are known, run on every release. Each run counts documents
        whose readers got wider, and a jump pages someone. The conversation store's chunk ids then say
        who received the page.'''))
    B.append(qa('Why not give the model a search tool and let it search until it is satisfied?',
        '''A loop handles two-step questions better. But each round adds a model call of about 0.7
        seconds and doubles the input tokens. And a poisoned chunk could steer the next search. So our code decides the searches.'''))
    B.append(qa('''"How many P1 tickets are open for payments?" or "Summarise this 40-page design doc."
        What happens?''',
        '''The classifier marks it as a count or a summary. A count becomes a query on the filter
        fields that every chunk record carries, under the same permission filter and final check. Our
        code counts, and the model never guesses. A summary gets a budget of its own: the whole
        document, up to about 30,000 tokens.'''))
    B.append(qa('An employee asks in German, and most documents are in English. What still works?',
        '''Vector search, if the embedding model was trained on many languages. Keyword search does
        not, so the rewrite model also writes an English version for it. The model answers in German
        from English chunks.'''))
    B.append(qa('''In a shared cell, one company uses the whole token limit all morning. What protects the
        others?''',
        '''Each company has its own token bucket inside the cell's, sized by its seats. It may borrow
        unused share up to a cap. Over its share, it goes to the fallback provider first. A company
        that keeps hitting its share moves to a cell of its own.'''))
    B.append(qa('''She loses access to a document an old answer cited. What does she see when she reopens
        the conversation?''',
        '''The text stays, but each citation is checked again when the conversation is shown. One she
        may no longer read loses its link and says "source no longer available to you". A turn that
        drew on it is never carried into a new prompt.'''))
    return B
