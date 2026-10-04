"""Part 3 and the end: what this system needs to run, one short section per question an interviewer
asks after the design, then the map and the technical round."""
from rag_v5_text import band, fold, fu, h2, qa, table, tx, ul


def body(fig):
    B = []
    B.append(band('Part 3', 'Running it'))

    # ---------------------------------------------------------------- where it runs
    B.append(h2('s-run', 'Where it runs: a cell in each company\'s area'))
    B.append(tx('''A region is one place where a cloud platform has data centres, such as Frankfurt. Its
        zones are separate buildings about a millisecond apart. Each company chooses a wider area for
        its data, such as the EU. Its cell runs across three zones of one region in that area, and
        keeps its backups in a second region there. Prompts go only to model endpoints inside the
        area, so its document text never leaves, not even for the fallback provider. One region is
        enough at 99.9%: a second live cell would double the cost to save a few hours in a rare
        regional outage.'''))
    B.append(fig(12, '''Top: dashed boxes are cells. Bottom: one question arriving in zone A, which holds
        every primary. A question arriving in B or C reads the primaries from there.'''))
    B.append(table(['part', 'where it runs', 'why'], [
        ['orchestrators, GPU pool, ingest workers', 'in all three zones, behind a load balancer',
         'stateless, so a dead zone loses a third of the capacity and nothing else'],
        ['the metadata database', 'one primary, a copy in each other zone', '''a commit waits until one
         copy has it. The identity provider never resends a change we accepted, so a removal lost
         with a dead primary would let a removed employee keep reading.'''],
        ['the search index', 'one copy of each shard in each zone', 'any copy answers reads'],
        ['Kafka', 'three copies of every message, one per zone', 'a change is never lost with a machine'],
        ['Redis, the conversation store', 'a primary and a copy', 'nothing in them is the only copy of anything that matters'],
    ]))
    B.append(fu(
        ('A company asks to move from the US to the EU. What moves?',
         '''Its whole cell, without embedding again. The bytes and vectors are copied, the EU database
         follows the US primary, and the index is rebuilt from the vectors in about 3 hours. The
         switch pauses US writes for seconds. Then the US copies are deleted.''')))

    # ---------------------------------------------------------------- split
    B.append(h2('s-cap', 'In a network split: only the final check refuses'))
    B.append(tx('''In a <b>network split</b> (a partition), two groups of machines cannot reach each other.
        The <b>CAP theorem</b> says each part must then choose. <b>Consistency:</b> every read sees the
        latest committed truth. <b>Availability:</b> every request gets an answer, perhaps a stale
        one. Ask of each part: if it is cut off, what does she see?'''))
    B.append(table(['part', 'chooses', 'what employees see when only this part is cut off'], [
        ['the final check, on the database primary', 'consistency', '''A zone that cannot reach the
         primary refuses, and the load balancer moves its questions to a zone that can. A primary cut
         off from the other zones turns read-only before a copy is promoted.'''],
        ['the search index', 'availability', '''A cut-off copy answers from what it holds. That is
         safe, because the final check comes after it.'''],
        ['Redis', 'availability', 'A stale principal list only affects recall.'],
        ['ingest', 'availability', 'Changes wait in Kafka and apply when the split heals, in order.'],
        ['the identity sync', 'consistency', '''It answers an error while it cannot commit. The identity
         provider retries, and a nightly full sync catches the rest.'''],
        ['the conversation store', 'availability', 'The question is answered as a first turn and saved later.'],
    ]))
    B.append(fu(
        ('Why does every final check read the primary, even from another zone?',
         '''A copy in its own zone can lag a removal, and the final check is the one step that must be
         exact. The primary is only a millisecond away. The cost: a failover of the primary refuses
         questions in every zone for about 30 seconds.''')))

    # ---------------------------------------------------------------- when it breaks
    B.append(h2('s-break', 'When something breaks: the model provider first'))
    B.append(tx('''<b>RPO</b> is the data a failure loses. <b>RTO</b> is the time until service returns. For
        a lost machine or zone, RPO is zero, because the database and Kafka confirm a write only once
        another zone has it.'''))
    B.append(tx('''The model provider fails most often, so the model router has a <b>circuit breaker</b>
        per provider. <b>Closed:</b> calls pass. <b>Open:</b> calls go to the fallback.
        <b>Half open:</b> a few trial calls test the provider.'''))
    B.append(fig(13, 'A 529 is the provider\'s "overloaded" error.'))
    B.append(table(['what fails', 'what employees see meanwhile', 'recovery', 'back in (RTO)'], [
        ['the model provider', '''A 3-second wait for questions in the first 10 seconds. Then the
         breaker opens (more than half the calls in 10 seconds failed, with at least 20 calls) and the
         fallback provider answers.''', 'a probe every 30 seconds until the provider answers again', 'when it recovers'],
        ['both providers', 'A search-only answer: the 8 checked chunks as links. Never an error.', 'the same probes', 'when one recovers'],
        ['an orchestrator, mid-answer', '''Her stream stops. The turn stops updating, so after 10
         seconds it is marked failed, and the browser asks again with a new turn id.''', 'the load balancer stops sending it questions', 'seconds'],
        ['the GPU pool, or one of its models', '''No embedding model: keyword search only. No reranker:
         fused order, no abstaining. No checker: citations marked "not checked".''', 'replace or add GPUs', 'minutes'],
        ['one index node', 'Nothing. The two other copies answer.', 'the engine copies the shard from a peer', 'about 30 minutes'],
        ['the whole index, corrupted', 'No answers.', '''restore the last snapshot, taken every 6 hours,
         then rewrite every document committed since, from the stored vectors''', '1 to 2 hours'],
        ['the metadata database\'s primary', '"I can\'t check permissions right now" for about 30 seconds.', 'the copy that holds every acknowledged commit is promoted', 'about 30 s'],
        ['Redis', '''Principal lists come from the database, and the answer cache is skipped. Each
         orchestrator counts its own share of each provider limit.''', 'a copy is promoted', 'seconds'],
        ['a source\'s API, or the identity provider', '''That source's edits wait, and the ingest-lag
         alarm fires. Signed-in employees keep asking.''', 'catch up from the cursor, or apply the changes on its return', 'when it recovers'],
        ['a whole zone', '''Its open answers stop, and the browsers ask again. Add 30 seconds of refused
         final checks if it held the database primary.''', 'the other zones\' orchestrators, 8 GPUs and two copies of each shard', 'seconds to 30 s'],
        ['the cell\'s whole region', 'No answers. Employees open documents in their sources.', '''restore in
         the area's second region from its copies of object storage and the database backups, then
         build the index from the stored vectors''', 'about 4 hours, mostly the index'],
    ]))
    B.append(tx('''Three index copies protect against a lost machine, not a bad change, which reaches all
        three at once. That is why a change builds a new index (Part 2, Every change is checked). A
        regional restore of about 4 hours uses up the month's 45-minute budget. We accept that, because
        it is rare.'''))
    B.append(tx('''<b>The metadata database</b> keeps a nightly backup plus its write-ahead log, the record of
        every change. So it can be restored to the last minute, instead of rebuilt from the sources
        in 4 days. Three repairs follow a restore:'''))
    B.append(ul(
        '''Every fetch ticket is raised by a million. The restore set tickets back below the versions the
        index holds, and the index would refuse the next writes.''',
        'The cursors are rewound, so the connectors re-read every change since.',
        '''The daily sweep and a full identity sync run at once, for the deletes and group changes no
        one resends.'''))
    B.append(fu(
        ('One index node is slow, not down. What happens to every question?',
         '''Each question asks all 4 shards, so one slow copy would slow them all. A shard still
         searching after 80 ms is asked again on its copy in another zone, and the first answer wins.
         A shard silent at 150 ms is left out.'''),
        ('How do you know the backup works?',
         'We restore it into a test cell every month and run the golden set against it.')))

    # ---------------------------------------------------------------- how it grows
    B.append(h2('s-grow', 'How it grows: ten times the questions, or ten times the documents'))
    B.append(tx('''Interviewers ask "what happens at 10 times the load?". Ask back: 10 times the
        questions, or 10 times the documents? Then answer part by part.'''))
    B.append(table(['part', 'runs out first', 'how it grows', 'at ten times today'], [
        ['the model provider', '''input tokens: about 300,000 a second at the peak. The first limit at 10
         times the questions.''', '''a higher limit from the provider, and ordinary questions to a smaller
         model''', '3 million a second: split across providers and models'],
        ['the GPU pool', 'reranker pairs: 5,000 a second', 'more GPUs, or rerank 50 instead of 100', 'about 50 busy GPUs, or about 30 reranking 50'],
        ['the search index', '''RAM: about 120 GB a copy. The first limit at 10 times the
         documents.''', '''more shards, as a new index built beside the old one, because splitting in
         place blocks writes''', '''1 billion chunks: 40 shards, or one bit a number in RAM, rescored
         from SSD'''],
        ['the metadata database', '''write bursts: a new company's first load, or a mass delete, writes
         millions of rows''', '''batch them a thousand to a transaction. Reads are one small query a
         question, about 50 a second, which is nothing.''', 'the same'],
        ['the connectors', 'each source\'s API quota, about 30 documents a second', 'higher quotas from the sources', '100 million documents take about 40 days to load'],
        ['orchestrators and ingest workers', 'nothing: stateless', 'add servers behind the load balancer, and workers up to the Kafka partition count', 'more of the same'],
    ]))
    B.append(tx('''<b>Backpressure.</b> Above the planned peak, each employee may ask at most 60 questions
        an hour. A question whose provider bucket is empty waits up to 2 seconds, then goes to the
        fallback provider. Ingest workers pull from Kafka at their own pace. So a burst of edits waits
        in the queue instead of overloading the sources or the index.'''))
    B.append(tx('''<b>Noisy neighbours.</b> In a shared cell, each company has its own token bucket inside
        the cell's, sized by its seats. It may borrow unused share up to a cap. Over its share, it goes
        to the fallback provider first, so the others do not. The reranker's queue takes each company's
        work in turn. A company that keeps hitting its share moves to a cell of its own.'''))
    B.append(fu(
        ('A new company connects 10 million documents on Monday. When can its employees ask?',
         '''After about a day, because the most recently edited documents load first. One source gives
         about 30 documents a second, about 2.5 million a day, so 10 million take about 4 days.
         Embedding them takes only hours. They come through a separate backfill topic, so the load
         never delays anyone's edits.''')))

    # ---------------------------------------------------------------- ledgers
    B.append(h2('s-ledger', 'Where the second goes, and where the cents go'))
    B.append(tx('''Interviewers ask for these two ledgers, usually as "where would you cut?". First, the
        time to Asha's first word:'''))
    B.append(table(['step', 'takes', 'clock'], [
        ['save her turn, read her principals, embed and classify the question', 'about 20 ms', '20 ms'],
        ['vector and keyword searches on all 4 shards, side by side, then fusion', 'about 40 ms', '60 ms'],
        ['the reranker scores up to 100 candidates', 'about 90 ms', '150 ms'],
        ['the final check on 20 ids, then pack the prompt', 'about 5 ms', '155 ms'],
        ['the provider reads 6,000 tokens and writes its first word', 'about 700 ms', '0.9 s'],
        ['a follow-up adds the rewrite before the searches', '+ 400 ms', '1.3 s'],
    ]))
    B.append(tx('''Most of the second is the provider's. To reach half a second, the lever is a smaller,
        faster model for ordinary questions. Second, the cost: about 2.5 ¢ an answer, three quarters
        of it input tokens, so every lever is about fewer input tokens, or cheaper ones.'''))
    B.append(table(['lever', 'what it saves'], [
        ['the provider caches the 1,100 instruction tokens that open every prompt (a tenth of the price)', 'about 0.3 ¢ an answer, $1,500 a day'],
        ['8 chunks after the reranker, not 20 (row N3)', 'about $9,000 a day'],
        ['no model call when the best score is below 0.3', 'a whole call per unanswerable question'],
        ['a small rewrite model, not the large one', 'about $1,000 a day'],
        ['the answer cache serves about 20,000 first turns a day', 'about $500 a day, and those start in 0.2 s'],
        ['the whole bill', '''tokens about $12,000 a day. Our own machines, 12 GPUs and about 30 servers,
         about $1,500 a day. About $2.50 an employee a month.'''],
    ]))
    B.append(fu(
        ('Cost per answer jumps from 2.5 to 3.5 cents overnight. Where do you look?',
         '''First at the trace log's tokens per turn by part of the prompt, where longer chunks or
         summaries show. Then at the fallback provider's share of questions. Last at answer length and
         the answer cache's hit rate.''')))

    # ---------------------------------------------------------------- security
    B.append(h2('s-sec', 'Security, privacy, and what we keep for how long'))
    B.append(tx('''Permissions are the big one, and Part 2 covered them. Interviewers also ask about the
        rest. Have one line for each:'''))
    B.append(ul(
        '''<b>Identity.</b> The company's single sign-on. Who she is comes from her session, and her
        principals from our records. Deactivation in the identity provider means 401 on her next
        call.''',
        '''<b>In transit and at rest.</b> TLS on every connection, including between our own
        services. Every store is encrypted with a key per company, so a company that leaves is a
        deleted key.''',
        '''<b>The provider.</b> Zero retention by contract: it keeps no prompts and trains on none.
        Endpoints inside the company's area only. No secrets in prompts: chunks that match a secret
        pattern (keys, tokens) are masked at ingest.''',
        '''<b>Audit.</b> Every turn stores the ids of the chunks its prompt held. "Who saw this document
        through the assistant?" is one query. Our staff reach a company's data only through audited
        emergency access, which the company can see.''',
        '''<b>Over-shared documents.</b> The assistant turns a forgotten mistake into a one-line answer.
        So admins can exclude folders and sensitivity labels from indexing, and a weekly report lists
        widely shared documents that match sensitive terms.''',
        '''<b>Abuse.</b> 60 questions an hour per employee, and a company's own token bucket. The chat
        page clicks only cited links and loads no images (Part 2, A document that gives orders).'''))
    B.append(table(['what we keep', 'for how long', 'why'], [
        ['raw bytes, parsed text, vectors (object storage)', 'old versions 90 days, a legal delete at once', 'to re-chunk or re-embed without reading the sources again'],
        ['conversations and turns', '90 days, then dropped by daily partition', 'history for the employee. The chunk ids are the audit trail.'],
        ['the trace log', '30 days, personal details removed', 'debugging and the monthly golden-set sample'],
        ['the golden set', 'until replaced', 'labelled with consent, personal details removed'],
        ['a deactivated employee', 'conversations kept to the 90 days, then gone', 'her principals are gone at once, so nothing new can be asked'],
    ]))

    # ---------------------------------------------------------------- rollout and watch
    B.append(h2('s-watch', 'Rollout, and what to watch'))
    B.append(ul(
        '''<b>Code ships zone by zone.</b> A server being replaced takes no new turns and lets its
        streams finish, for at most 60 seconds. If a zone's error rate rises, the rollout stops
        there.''',
        '''<b>Schema changes</b> add columns first and drop old ones a release later, so two versions
        of the code can run at once.''',
        '''<b>Prompts, chunkers, embedding models and model ids</b> go through the three checks in
        Part 2, and one row switches them and rolls them back.''',
        '''<b>A model version is pinned</b> by its exact id, never "latest", which the provider could
        move to an untested model.'''))
    B.append(tx('''One trace id follows each turn through every service and the provider call. The SLO
        is: 99.9% of questions get an answer, a search-only answer or "not found" within 10 seconds.
        That leaves about 45 minutes of error budget a month. Four numbers tell the health: time to
        first word, final-check refusals, ingest lag, and thumbs-down.'''))
    B.append(table(['watch', 'page someone when'], [
        ['the first word, 95th percentile', 'above 2 seconds for 10 minutes'],
        ['the model router\'s breakers', 'a breaker opens'],
        ['questions refused by the final check', 'more than 1 in 1,000 for 5 minutes: the database primary is slow or out of reach'],
        ['chunks dropped by the final check', 'more than 2% for 15 minutes: the index or the cached principal lists lag'],
        ['ingest lag, from edit to searchable, 95th percentile', 'above 5 minutes for 15 minutes'],
        ['citations failing the check', '50% above the 7-day average, for an hour'],
        ['cost per answer', 'above 3 cents for an hour'],
        ['thumbs-down per 100 answers', 'up by 2 points for an hour'],
    ]))
    B.append(fu(
        ('A manager says yesterday\'s answer was wrong. How do you find which step failed?',
         '''Start from the message id. The trace log keeps one record per turn with every step's
         inputs and outputs. Was the rewritten question right? Someone who knows the subject names
         the chunk that answers. Was it among the 100 candidates (recall), the reranker's 20
         (ranking), the 8 packed (packing)? Was it cited, and what did the checker say? Each failed
         step points to a different fix, and the question joins the golden set.''')))

    # ================================================================ End
    B.append(band('End', 'Remember it'))
    B.append(h2('s-recap', 'Remember it: the whole page on one map, and the technical round'))
    B.append(tx('If you can redraw this map from memory, you can rebuild the page.'))
    B.append(fig(14, '''To test yourself, read only the coloured word that starts each line, say the rest
        from memory, then check. Do it on day 1, 3, 7 and 10.'''))
    B.append(fold('The technical round: five questions interviewers push on', 'the last round',
        qa('''A connector maps a restricted page as readable by all staff. The search filter and the
           final check both trust that row. What catches it?''',
           '''Neither can, so it is caught where permissions are written. Each connector ships with a
           permission test suite, sample documents whose readers are known, run on every release. Each
           run also counts documents whose readers got wider, and a jump pages someone. The
           conversation store's chunk ids then say who received the page.''')
        + qa('A folder of salaries was shared with all staff by mistake years ago. Who can find it now?',
           '''Everyone, because the source allows it. The assistant would turn a forgotten mistake into
           a one-line answer. So admins can exclude folders or sensitivity labels from indexing, and a
           weekly report lists widely shared documents that match sensitive terms. A file shared only
           by link never becomes a principal: a link is not a permission to be found.''')
        + qa('Why not give the model a search tool and let it search until it is satisfied?',
           '''A loop handles two-hop questions better. But each round adds a model call of about 0.7
           seconds and doubles the input tokens, and a poisoned chunk could steer the next search. So
           our code decides the searches. If two-hop questions become common in the golden set, that
           changes.''')
        + qa('''"How many P1 tickets are open for payments?" or "Summarise this 40-page design doc."
           What happens?''',
           '''The classifier marks it as a count or a summary. A count becomes a query on the filter
           fields every chunk record carries, under the same permission filter and final check. Our
           code counts, once per document, and the model never guesses. A summary gets a budget of
           its own: the whole document, up to about 30,000 tokens. A longer one is summarised section
           by section.''')
        + qa('An employee asks in German, and most documents are in English. What still works?',
           '''Vector search, if the embedding model was trained on many languages, because the same
           meaning lands nearby whatever the language. Keyword search does not. So the rewrite model
           also writes an English version for it, and the model answers in German from English
           chunks.''')))
    return B
