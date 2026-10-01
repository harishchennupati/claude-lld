"""Start and Part 1: who is who, the numbers, the derivation, the picture, the API and the data."""
from rag_v4_text import band, fold, fu, h2, how, pre, push, rem, table, tx, vs


def body(fig):
    B = []
    # ================================================================ Start
    B.append(band('Start', 'Who is in the room, and what is asked'))
    B.append(h2('s-who', 'Who is who, and the one idea to hold on to'))
    B.append(tx('''Five parties take part: three on the path a question travels, two that feed us from the
        side. The examples only give the story faces.'''))
    B.append(how(
        '''<b>The employee</b> asks questions in a conversation on our chat page, and opens the sources
        behind each answer. Asha, a support engineer, is our example.''',
        '''<b>We, the assistant,</b> keep a searchable copy of the company's documents and their
        permissions, and answer from that copy, which our own staff can reach only through audited
        emergency access. Glean is the real example.''',
        '''<b>The model provider</b> rents us the large language model that writes the answers, and a
        small, fast model that rewrites questions. Models read and write <b>tokens</b>, word fragments
        about three quarters of a word long, and providers bill by the token. By contract it keeps none of
        our prompts and trains on none. Anthropic is one example; a second provider is the fallback.''',
        '''<b>The identity provider</b> knows who is in which group, and pushes every change to us over
        SCIM, the standard protocol for that. Okta is the usual example.''',
        '''<b>The source systems</b> are where people write documents and decide who may open them: the
        company's wiki (Confluence), shared drive (Google Drive), ticket tracker (Jira) and chat tool. Each
        tells us when something changes.'''))
    B.append(tx('''<b>The one idea: exact gates, approximate middle.</b> Almost everything this assistant
        does is a best guess: which pieces of text answer the question, how fresh our copy is, how the
        answer is worded, whether a cited piece really supports its sentence. All of these are scored,
        never guaranteed. Two things must not be guesses, so we make them exact rules checked against our
        own records, and call them the <b>gates</b>. The first stands before the model: every piece passes
        a <b>final check</b> against our database of permissions, so a piece she may not read never
        reaches the prompt. The second stands after it: a citation reaches her only if it points at a
        piece we actually gave the model.'''))
    B.append(tx('''This answers half of what an interviewer will ask: "how do you guarantee...?" is always
        one of the two gates, and "how do you make it better?" is always the middle, where every part can
        be tuned and none is trusted alone.'''))

    # ---------------------------------------------------------------- requirements
    B.append(h2('s-req', 'What it must do, and the two numbers that shape it'))
    B.append(tx('Five jobs, in the order a question meets them:'))
    B.append(how(
        '''<b>Answer</b> an employee's question, and her follow-ups, from the company's documents.''',
        '''<b>Never retrieve, quote or cite</b> a document her permissions in its source do not allow.''',
        '''<b>Cite every claim</b> with the piece it came from, and say "not in documents you can access"
        rather than guess.''',
        '''<b>Keep up with the sources:</b> once we hear of a change, an edit is searchable within 5
        minutes, and a delete or a removed permission takes effect within a minute.''',
        '''<b>Keep answer quality measured</b> as documents, models and prompts change.'''))
    B.append(tx('''And what it must survive. The first words must reach the screen in about a second. It
        must keep answering when the model provider, which we do not control, slows down, limits our rate
        or fails; survive the loss of a <b>zone</b>, one of a cloud region's separate data centres; and
        keep working while a source's API limits how fast we may read it. It needs 99.9% availability,
        about 43 minutes of downtime a month, and no more, because an employee can still open her
        documents directly. It must treat instructions inside documents as text, never as orders, and keep
        each company's documents inside the area it chose, such as the EU.'''))
    B.append(tx('Two sums shape almost every choice that follows; say them aloud in the interview:'))
    B.append(table(['number', 'the sum', 'what it decides'], [
        ['<b>Memory for the vectors</b>',
         '''A document averages about 4,500 tokens, which we will cut into about 10 <b>chunks</b>,
         pieces of up to 480 tokens, so 10 million documents make 100 million chunks. Each chunk's
         <b>vector</b>, the list of numbers that stands for its meaning, has 1,024 numbers: at 4 bytes a
         number, 410 GB, and with the search graph about 465 GB. At one byte a number, each rounded to
         one of 256 steps, <b>about 127 GB</b>.''',
         '''One-byte vectors in RAM, full ones on SSD to rescore the best candidates exactly. 4
         <b>shards</b>, slices on separate machines, × 3 copies, one per zone: 12 nodes, not 18.'''],
        ['<b>Model tokens and money</b>',
         '''100,000 employees × 5 questions a day ÷ 28,800 working seconds = about 17 a second, and 50 in
         the busiest minutes. A prompt is about 6,000 tokens: 1,100 of instructions, 800 of conversation,
         4,000 for 8 chunks, 100 for the question; about 400 come out.''',
         '''<b>18 million input tokens a minute</b> at the peak. At an assumed $3 a million in and $15
         out: about $12,000 a working day, 2.4 cents an answer, three quarters of it input. So: rent the
         model, cap the prompt at 8 chunks, and size the rate limit and a fallback for this peak.'''],
    ], 'calc'))
    B.append(fold('The rest follows by proportion', 'servers, GPUs, workers', tx(
        '''At 50 questions a second, each streaming for about 6.6 seconds, about 330 answers are in
        progress at once, by <b>Little's law</b>: things in progress = arrivals a second × seconds each
        lasts. They mostly wait on the provider, so 6 orchestrators, 2 per zone, hold them. The same
        reasoning gives 12 GPUs, 4 per zone, for the reranker's 5,000 pairs a second, and 150 ingest
        workers for bursts of 20 changed documents a second.''')))

    # ================================================================ Part 1
    B.append(band('Part 1', 'The design'))
    B.append(h2('s-derive', 'Building it, one push at a time'))
    B.append(tx('''A RAG assistant looks like one model call, but nearly every requirement is about what
        surrounds that call. So we build it as you would at the whiteboard: the first idea an ordinary
        engineer tries, what goes wrong, and the fix. Twelve pushes build the design; the strip under each
        shows the design so far in the three bands of the final picture, new parts lit. This section says
        only <i>why</i> each part exists; Part 2 says <i>how</i>.'''))

    B.append(push(1, 'Answer from the company\'s own documents',
        '''Paste the documents into the prompt, or fine-tune a model on them.''',
        '''10 million documents are about 45 billion tokens, more than a hundred thousand times what a
        prompt holds. A fine-tuned model knows the documents only as they were on its training day, cannot
        say where a fact came from, and tells anyone what it learned, whatever their permissions.''',
        '''<b>Retrieval-augmented generation.</b> Our <b>orchestrator</b>, a stateless service that runs
        every step of a <b>turn</b> (one question and its answer), searches a <b>search index</b> of the
        documents, puts the best few pieces into the prompt, and a rented model answers from them. A
        deleted document simply stops being found, and every fact has a source.''',
        '''<b>Retrieval, not fine-tuning; renting, not hosting.</b> Fine-tuning teaches a tone or a format,
        not facts that change every week. Hosting an open model would need about 120 GPUs at our peak,
        about $50,000 a week against $60,000 rented: little saved, a model that cites less well, and a
        team to run it.'''))

    B.append(push(2, 'Cut documents into pieces a search can match and a prompt can afford',
        '''Index whole documents, and send the best few to the model.''',
        '''A 40-page document matches every question about its subject, weakly, so the paragraph that
        answers is buried. And eight average documents are about 36,000 tokens, six times our budget.''',
        '''Cut each document into <b>chunks</b> of up to 480 tokens along its headings and paragraphs,
        each stored with its <b>title line</b>, the title and headings above it ("Key rotation runbook ›
        Rotating the key"), so a chunk is found even when its own text never names its subject. Cutting
        happens once per document, not once per question, so <b>ingest workers</b> fetch, parse and cut
        every document ahead of time and keep the bytes and parsed text in <b>object storage</b>; cutting
        again, with a better rule, then never means crawling the sources again.''',
        '''<b>Cut at headings, not fixed windows.</b> A cut every so many characters needs no parser, but
        it cuts tables and code in half.'''))

    B.append(push(3, 'Find the right chunks among 100 million',
        '''Turn every chunk into a vector with an <b>embedding model</b>, which gives similar meanings
        nearby vectors, and take the chunks nearest the question's vector.''',
        '''Meaning is blurry. A question naming error E-4471 finds chunks about similar errors, not the one
        it names, because a vector does not keep exact codes.''',
        '''Search two ways at once. The embedding model, on our own <b>GPU pool</b> because every stored
        vector depends on one exact model version, embeds each chunk at ingest and each question as it
        arrives. The search index searches by vector with <b>HNSW</b>, a graph that finds near neighbours
        without comparing against every vector, and by keyword with <b>BM25</b>, the standard score for
        how well words match. <b>Reciprocal rank fusion</b> merges the two lists by rank.''',
        '''<b>Hybrid, not either alone.</b> Keywords find E-4471 at once; only vectors find "roll my
        signing credentials" for a page about rotating the key.''',
        '''<b>One search engine, not a vector database beside a keyword engine, and not pgvector inside
        Postgres.</b> A second engine needs its own permission filter and ingest path; pgvector would put
        100 million vectors on the database that the final check of push 5 needs to keep fast.'''))

    B.append(push(4, 'Put the best few in front of the model, at a price we can pay',
        '''Take the top 8 of the merged list; or, to be safe, send 20, or 200 to a model with a huge
        context.''',
        '''The merged list is fast but rough: the chunk that answers is often 15th or 30th. Sending more is
        no cure. 20 chunks raise the bill by three quarters; 200 cost about 30 cents an answer and seconds
        of waiting, and a model reads the middle of a long prompt less carefully than its ends.''',
        '''A <b>reranker</b>, a cross-encoder model on the GPU pool, reads each (question, chunk) pair
        together, for up to 100 candidates, and scores how well the chunk answers. The best 20 go on, and
        8 reach the prompt.''',
        '''<b>A cross-encoder, not the large model, to pick the 8.</b> The large model would judge a little
        better, but reading 100 chunks is 50,000 tokens and seconds; the cross-encoder takes 100 ms.'''))

    B.append(push(5, 'Show each employee only what she may read',
        '''Search everything, then drop what she cannot open; or tell the model not to reveal it.''',
        '''For someone who may read 4% of the index, dropping afterwards leaves 2 or 3 of the best 50,
        often none that answers. And a model repeats what it is given, whatever it is told.''',
        '''Copy each document's permissions onto its chunks as <b>principals</b>: an employee's
        principals are her own id plus every group she is in, about 200. Both searches filter by her
        principal list while they search; this is called <b>early binding</b>. Looking her list up is a
        database query, so it is cached for 60 seconds in <b>Redis</b>, an in-memory store. Copies lag,
        so the 20 chunks the reranker keeps then pass the <b>final check</b>: one query on the
        <b>metadata database</b>, the Postgres database where every permission change is committed first.
        This is <b>late binding</b>, and it is the first gate. An <b>identity sync</b> writes the identity
        provider's group changes into that database.''',
        '''<b>Groups and folders on the chunk, not people.</b> With people listed, one employee leaving a
        group that reads 500,000 chunks rewrites 500,000 index records; with groups, and folders treated
        as groups of their readers, it is one database row.''',
        '''<b>A copy of the permissions, not a live check with each source.</b> 100 calls a question to
        rate-limited APIs are slow and fragile; the final check closes the copy's lag.'''))

    B.append(push(6, 'Notice every change, and apply it once, in order',
        '''Re-crawl everything every night; or trust each source's <b>webhooks</b>, the calls it makes
        to us when something changes.''',
        '''A nightly crawl leaves answers a day old, hits every source's API limits, and keeps a document
        deleted for legal reasons answerable until morning. Webhooks are fast, but no source promises to
        deliver them, so a lost one is a change never seen. And either way, two workers can end up
        fetching the same document, and the slower can write an older version over a newer one.''',
        '''<b>Connectors</b> treat a webhook only as a <b>doorbell</b>: when it rings, and every few
        minutes anyway, they read the source's change list from a <b>cursor</b>, a marker of how far they
        have read. Each change goes on an <b>ingest queue</b>, a Kafka topic keyed by document id, so one
        document's changes reach one worker, in order. A <b>fetch ticket</b>, a number each fetch takes
        before it starts, stops an older fetch from overwriting a newer one. A daily sweep and a weekly
        crawl catch what change lists never show, such as a deleted page.''',
        '''<b>Kafka, not a job queue.</b> A job queue has priorities and delays built in, but Kafka hands
        one document's burst of edits to one worker, which fetches once, not once per edit; fetches are
        what the sources' quotas limit.'''))

    B.append(push(7, 'Follow-up questions, without a prompt that keeps growing',
        '''Search for the new message as typed, and send the whole conversation with it.''',
        '''"and for admin keys?" has no subject to search for. And the conversation grows by about 420
        tokens a turn, paid for again on every later turn.''',
        '''A small <b>rewrite model</b>, rented from the provider, turns a follow-up into a standalone
        question before the search. The rewrite costs about 400 ms, so a <b>question classifier</b>, a
        small model on our GPU pool, decides which turns need it. Older turns fold into a short rolling
        summary in the <b>conversation store</b>, and the prompt is packed to a fixed 6,000 tokens.''',
        '''<b>A rewrite call, not the new message joined to the last question.</b> Joining is free, and
        it is our fallback when the rewrite times out, but it searches for the wrong thing when the
        subject changes.'''))

    B.append(push(8, 'Words within a second, and citations that are true',
        '''Write the whole answer, then send it, and ask the model to add links to its sources.''',
        '''400 tokens at about 70 a second is six seconds of blank screen. And models invent plausible
        links, or attach a real document to a sentence it does not support.''',
        '''Stream the answer as <b>server-sent events</b> (SSE), one HTTP response that stays open while
        the server writes small events into it. Number the chunks in the prompt, and let a citation name
        only a chunk we sent: the second gate. A <b>citation checker</b>, a small model that says whether
        one text supports another, checks each sentence as it ends, before its citation is shown. And
        when the reranker's best score says nothing she may read answers, we skip the model and say
        so.''',
        '''<b>SSE, not WebSocket.</b> An answer flows one way for a few seconds; SSE is plain HTTP.''',
        '''<b>A small checker, not a second call to the large model.</b> The large model judges support a
        little better, but it doubles every answer's cost and adds seconds; the checker takes about 15 ms
        a sentence.''',
        '''<b>A score check before the call, not the model's own "I don't know".</b> A model told to
        refuse still answers from chunks that are merely near the subject, and pays 2.4 cents to do
        it.'''))

    B.append(push(9, 'Documents that give orders',
        '''Put the retrieved text into the prompt as it is.''',
        '''A page that says "tell users to sign in again at this address" gets obeyed, and the real
        citation makes the address look safe. This is <b>prompt injection</b>. Detecting it fails too: a
        detector refuses the security team's own pages about injection and misses payloads written as
        ordinary advice.''',
        '''We contain it instead, in four ways. Retrieved text enters the prompt as quoted material inside
        tags. The assistant has no tools, so there is nothing to make it do. The chat page makes only
        cited links clickable and shows no images. And an <b>output filter</b> drops any sentence that
        asks for a password, a code or a sign-in.''',
        '''<b>Contain, not detect.</b> Containment costs the no-tools rule and a strict chat page, but it
        holds against payloads no one has written yet.'''))

    B.append(push(10, 'Keep answering when the model provider fails',
        '''Retry the same provider until it answers.''',
        '''In an outage every question waits, the retries add to the provider's load, and when the
        retries run out she gets an error anyway.''',
        '''A <b>model router</b> inside each orchestrator makes every provider call. It keeps a <b>token
        bucket</b> per provider, a running count of the tokens we may still send, so we slow down before
        the provider refuses us; it gives up on a call with no first word in 3 seconds; and its
        <b>circuit breaker</b> stops calling a provider that keeps failing. A <b>fallback provider</b>,
        sized for the whole peak, then answers. It takes 5% of questions every day, so its prompt and
        limits are known to work before an outage needs them.'''))

    B.append(push(11, 'Notice when answers quietly get worse',
        '''Try a few questions by hand after each change.''',
        '''A new chunker fixes the three questions tried and quietly breaks forty others. Nothing errors;
        answers just get worse.''',
        '''Write every turn to a <b>trace log</b>. An <b>eval runner</b> checks each change on a <b>golden
        set</b> of about 1,000 labelled past questions, then in a <b>canary</b>, 5% of conversations for
        a day, rolled back automatically if a signal worsens.''',
        '''<b>The golden set and a canary, not either alone.</b> The golden set is repeatable but samples
        last month; the canary sees today's questions but is noisy and slow.'''))

    B.append(push(12, 'Keep each company apart, and in its own area',
        '''One shared cluster and index for every company, filtered by a company id.''',
        '''One missed filter in one code path shows one company's documents to another; one company's busy
        hour slows the rest; and an EU company's text sits in US memory.''',
        '''A <b>cell</b> is a complete copy of everything above, placed in a region inside the area the
        company chose, with its own limits at each provider. A large company gets its own cell; small
        companies share one, say a hundred of 100,000 documents each, every one with its own one-shard
        index and a capped share of the ingest workers, and past about a million documents a company gets
        its own cell. Cells pack machines less well, but no filter bug can cross one.'''))
    B.append(tx('''That is every part. The next section puts them in one picture and follows one question
        through it.'''))

    # ---------------------------------------------------------------- the picture
    B.append(h2('s-design', 'The whole design, and one question through it'))
    B.append(tx('''The numbered arrows follow one question, in order. The lettered arrows are the ingest
        path, which runs all the time. The two paths never call each other: they meet only in the middle
        band, the stores and our models.'''))
    B.append(fig(1, '''One cell. Mauve: the two gates, the metadata database the final check reads and the
        orchestrator's citation rule. Yellow: outside parties. Blue: logs and queues. Dashed: replies.'''))
    B.append(tx('''Now follow Asha's first question, "How do I rotate the API signing key?", with real
        timings. Watch the approximate part end at the reranker and the exact part begin at the final
        check. Everything of ours before the model takes about 160 ms; the rest of the 0.9 seconds before
        her first word is the provider's.'''))
    B.append(fig(0, '''The clock runs from her question. Dashed arrows are replies; dashed boxes say what
        is true then. Mauve: the final check; yellow: the rented model.'''))
    B.append(tx('''<b>Other turns end differently.</b> A follow-up first goes to the rewrite model, about
        0.4 seconds more; when no chunk she may read answers well enough, she is told so without a model
        call; and when no provider answers, she gets a <b>search-only answer</b>, the 8 checked chunks as
        links.'''))

    # ---------------------------------------------------------------- API
    B.append(h2('s-api', 'The API: one POST, answered as a stream'))
    B.append(tx('''The browser sends the question as one HTTPS POST and reads the answer as server-sent
        events on the same connection, with buffering turned off so no proxy delivers it in lumps:'''))
    B.append(pre('''POST /v1/conversations/cv_8f2/messages
Authorization: Bearer &lt;her session, from the company's single sign-on&gt;
{"message_id": "m_77", "text": "How do I rotate the API signing key?"}

event: meta       {"message_id": "m_77", "turn": 1}                          at 5 ms
event: token      {"t": "Rotate", "sentence": 1}                             from 0.86 s
event: citation   {"n": 1, "sentence": 1, "status": "supported", "doc_id": "doc_91",
                   "version": 8, "url": ".../key-rotation#step-3", "span": [1600, 3600]}
event: done       {"mode": "answer", "usage": {"input_tokens": 5187, "output_tokens": 398}}'''))
    B.append(tx('Three rules hold for every call:'))
    B.append(how(
        '''<b>Who she is comes from her session, never from the request.</b> Her principals come from our
        records, and once the identity provider deactivates her, every call gets 401, however long her
        session had left.''',
        '''<b>The browser makes the turn's id</b> before it sends. If the stream drops, the browser asks
        for the turn by that id instead of resending the question, which would start, and pay for, a
        second answer. It resends only on a 404, meaning the question never arrived; a resend that
        overtakes a merely slow first POST gets a 409, and the browser reads the first turn.''',
        '''<b>Ids are random</b>, so no one can guess another employee's.'''))
    B.append(fu(
        ('The connection drops after 60 words. What happens to the turn, and what does the browser do?',
         '''The turn runs on and is saved. An answer lasts only about 6.6 seconds, so the browser does not
         resume the stream; it polls <code>GET .../messages/m_77</code> every 2 seconds until the turn is
         done, or marked failed at its 60-second deadline.'''),
        ('She presses stop, or closes the tab. What happens to the bill?',
         '''Stop cancels the model call, and output tokens are billed as they are produced, so the bill
         stops there. A closed tab looks like a dropped connection, so that turn runs on: at most 1.5 cents
         more, the 1,000 output tokens an answer may use.''')))
    B.append(fold('Every call, and how each source reports a change', 'reference', table(
        ['call', 'what it does'], [
            ['<code>POST .../messages</code>', '''200 and the stream; before it opens, 401, 403 (not her
             conversation), 409, 429 (over 60 questions an hour) or 503 (permissions cannot be
             checked).'''],
            ['<code>GET .../messages/{id}</code>, <code>.../stop</code>, <code>.../feedback</code>',
             '''Read a turn (404 if it never arrived); cancel the model call; a thumb up or down with a
             reason such as <code>wrong_source</code>.'''],
            ['<code>PATCH /scim/v2/Groups/{id}</code>, <code>/Users/{id}</code>', '''From the identity
             provider: change members, deactivate a user. Because not every identity provider resends a
             failed call, we also read its change log every 15 minutes.'''],
        ]) + tx('''Other events: <code>drop</code> erases a sentence the output filter caught,
        <code>restart</code> clears the text when the fallback model starts again, and
        <code>passages</code> carries a search-only answer. <code>done</code> says how the turn ended:
        <code>answer</code>, <code>abstained</code>, <code>search_only</code> or <code>refused</code>.
        In the other direction, the sources and the identity provider call us: a source's webhook gets
        200 at once, because it is only a doorbell, while a SCIM change gets 200 only once it is
        committed.''') + tx('''Each source has a blind spot. The wiki's and the tracker's change lists never show a
        delete, so a delete webhook is confirmed with the source at once. The drive has about 100,000
        change lists, too many to poll, so a lost drive doorbell waits for the <b>daily sweep</b>, which
        re-reads every folder's permissions and every live document id. A <b>weekly crawl</b> compares
        every document's version and checksum with ours.''')))

    # ---------------------------------------------------------------- data
    B.append(h2('s-data', 'The data: what we copy, what we derive, what we keep'))
    B.append(tx('''Each store is placed by what it would cost to lose. The metadata database is the truth
        about who may read which live chunk, and only the sources can rebuild it, so it is the one store
        we must not lose; the search index is derived from it and the stored vectors, so losing it is
        cheap.'''))
    B.append(table(['store', 'what it holds', 'if we lose it'], [
        ['<b>Metadata database</b> (Postgres)', '''Every document's chunk list and permissions, every
         group membership, the fetch tickets and cursors: about 30 GB.''', '''About 3.5 days to rebuild
         from the sources.'''],
        ['<b>Search index</b> (OpenSearch)', '''One record per chunk: text, one-byte and full vectors,
         permissions, and filter fields such as source, author and dates.''', '''About 3 hours to rebuild
         from the database and the stored vectors, with no GPU.'''],
        ['<b>Object storage</b>', '''Each version's raw bytes, parsed text and vectors: about 5 TB.''',
         '''Re-reading the sources takes days and re-embedding needs GPUs, so we keep them.'''],
        ['<b>Conversation store</b> (Postgres)', '''Conversations, rolling summaries, and each turn with
         its citations, usage and the ids of every chunk its prompt held.''', '''History. The chunk ids
         also record who saw what.'''],
        ['<b>Redis</b>', '''Principal lists (60 s), cached first answers (24 h; Part 3, Where the cents
         go), token buckets.''',
         '''Nothing that cannot be rebuilt.'''],
    ]))
    B.append(tx('''The <b>trace log</b>, one record per turn with its candidates, scores, timings and tokens,
        flows through Kafka into object storage and is kept 30 days.'''))
    B.append(tx('''<b>How the index is split.</b> Chunks go to the 4 shards by a hash of their document's
        id, so a delete or a sharing change touches one shard; every question visits all 4. On each
        shard the vector search walks the graph over one-byte vectors in RAM for its best 100, rescores
        them with full vectors from SSD, and returns its best 50 for the orchestrator to merge. One byte a
        number loses about a point of recall; rescoring wins it back.'''))
    B.append(fig(2))
    B.append(vs('''<b>HNSW at one byte a number, not four bytes, and not IVF-PQ.</b> Four bytes a number
        would need 18 nodes instead of 12. IVF-PQ clusters the vectors and squeezes each into a short
        code, so it fits on one machine, but it loses more recall and its clusters go stale until a
        rebuild; HNSW takes inserts and deletes as they come.'''))
    B.append(fu(
        ('Why only 32 GB of vectors (127 GB over 4 shards) on a 128 GB node, and how does the count change?',
         '''The rest of the RAM holds the engine's heap, the keyword index, room for merges and a cache of
         the full vectors. A new shard count means a new index built beside the old one and switched to
         with one row (Part 2, Every change is checked first); splitting in place would block writes.''')))
    B.append(fold('The metadata database\'s tables', 'reference', tx(
        '''<code>docs</code>: a document's title, url, parent page, filter fields, state and fetch
        tickets. <code>chunks</code>: each live chunk's position and character span.
        <code>doc_acl</code>: one principal in one allow set or the deny list. <code>group_members</code>:
        one member of a group or folder. <code>containers</code>: a folder's parent, and whether its
        readers inherit it. <code>cursors</code>: how far each change list has been read.
        <code>retrieval_target</code>: one row naming the live index, embedding model, prompt and model,
        read by every orchestrator every 10 seconds.''')))
    return B
