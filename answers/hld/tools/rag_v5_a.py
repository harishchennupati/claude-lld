"""Start and Part 1: who is who, the numbers, the chat stream, the picture with its derivation, the data."""
from rag_v5_text import band, fold, fu, h2, how, pre, table, tx, ul


def body(fig):
    B = []
    # ================================================================ Start
    B.append(band('Start', 'Who is in the room, and what is asked'))
    B.append(h2('s-who', 'Who is who, and one question from Enter to the last citation'))
    B.append(tx('''Five roles. The first three are on the path of a question. The last two feed us from
        the side. The examples only give the story faces.'''))
    B.append(how(
        '''<b>The employee</b> asks questions in a conversation on our chat page and opens the sources
        of each answer. Example: Asha, a support engineer.''',
        '''<b>Us, the assistant.</b> We keep a searchable copy of the company's documents with their
        permissions, and we answer from it. Our staff reach the copy only through audited emergency
        access. Example: Glean.''',
        '''<b>The model provider</b> rents us the language model that writes answers, and a small, fast
        model that rewrites questions. Models read and write <b>tokens</b>. A token is about three
        quarters of a word, and providers bill by the token. By contract, the provider keeps none of
        our prompts and trains on none. Example: Anthropic, with a second provider as the fallback.''',
        '''<b>The identity provider</b> knows who is in which group. It pushes every change to us over
        SCIM, the standard protocol for that. Example: Okta.''',
        '''<b>The source systems</b> are where people edit documents and set their permissions. Each
        tells us about changes. Examples: the Confluence wiki, Google Drive, Jira (its issues are
        "tickets" on this page) and a chat tool.'''))
    B.append(tx('''<b>Exact gates, approximate middle.</b> A <b>turn</b> is one question and its answer. A
        turn passes two gates. Both gates are rules checked against our records, so neither guesses.
        Everything between the gates is a best guess, scored and never guaranteed. That includes which
        chunks are relevant, how fresh an edit is, how the answer is worded, and whether a cited chunk
        supports its sentence.'''))
    B.append(ul(
        '''<b>Gate 1, before the model.</b> Every chunk goes through the <b>final check</b>. That is one
        query on our <b>metadata database</b>, which holds each document's chunk list and permissions.
        The check is final because it runs last, after searches that also filter by her permissions
        but may lag.''',
        '''<b>Gate 2, after the model.</b> A citation reaches her only if it names a chunk we gave the
        model.'''))
    B.append(tx('''<b>The parts, by name.</b> The <b>orchestrator</b> is our stateless service that runs
        every step of a turn. Her <b>principals</b> are her own id plus every group she is in, and each
        document's permissions are copied to us as lists of principals. An <b>embedding model</b> turns
        text into a <b>vector</b> of 1,024 numbers, and similar meanings get nearby vectors.'''))
    B.append(tx('''A <b>reranker</b>, a model on our GPUs, scores how well a chunk answers a question. The model
        writes the answer from the best 8 chunks and marks each sentence with the chunk it used. The
        <b>citation checker</b>, a small model on our GPUs, checks each citation as the answer
        streams.'''))
    B.append(fig(0, '''The clock runs from her question. Dashed arrows are replies. Dashed boxes say what
        is true then. Mauve: the final check. Yellow: the rented model.'''))
    B.append(tx('''<b>Other turns, other endings.</b> A follow-up first goes to the rewrite model, which
        makes it stand alone: about 0.4 seconds more (Part 2, Turn four). When no chunk she may read
        answers well enough, the assistant says so without a model call (Part 2, A citation). When no
        model provider answers, she gets a <b>search-only answer</b>: the 8 checked chunks as links
        (Part 3).'''))

    # ---------------------------------------------------------------- requirements
    B.append(h2('s-req', 'What the interviewer expects: five jobs, vector memory and tokens a second'))
    B.append(how(
        '''<b>Answer</b> an employee's question in a conversation, from the company's documents. The
        first words reach the screen in about a second.''',
        '''<b>Never show, quote or cite</b> a document that her permissions in its source do not
        allow.''',
        '''<b>Cite every claim</b> with the chunk it came from. Say "not in documents you can access"
        instead of guessing.''',
        '''<b>Keep up with the sources.</b> Once we hear of a change, an edit is searchable within 5
        minutes. A delete, or a removed permission, takes effect within a minute.''',
        '''<b>Keep answer quality checked</b> as documents, models and prompts change.'''))
    B.append(tx('What it must survive:'))
    B.append(ul(
        '''It keeps answering when a model provider slows down, limits our rate or fails. We do not
        control the provider.''',
        '''It survives the loss of a <b>zone</b>. A <b>region</b> is one cloud location, such as
        Frankfurt, and its zones are its separate data centres.''',
        '''It keeps working while a source's API limits our <b>connectors</b>, the programs that read
        the sources.''',
        '''It is available 99.9% of the time, about 45 minutes of downtime a month. Not more, because
        employees can still open their documents directly.''',
        '''It treats instructions inside documents as text, never as orders.''',
        '''It keeps each company's documents inside the area it chose, such as the EU.'''))
    B.append(tx('''<b>Two sums shape the design.</b> Round every input to one digit and say "about". The
        interviewer wants the size, not the decimals.'''))
    B.append(table(['number', 'how', 'result', 'what it decides'], [
        ['<b>RAM for the vectors</b>',
         '''10 million documents × 10 chunks each = 100 million chunks. A vector is 1,024 numbers.
         At 1 byte a number, a vector is 1 KB, so 100 million vectors are 100 GB. The search graph
         adds about 20%. At 4 bytes a number it is four times that.''',
         '''<b>about 120 GB a copy</b> at one byte a number, instead of about 450 GB''',
         '''One byte a number in RAM. The full vectors stay on SSD to rescore the best candidates
         (score them again exactly). Four <b>shards</b>, slices of the index, of about 30 GB each, one
         per 128 GB node. Three copies of each shard, one per zone: 12 nodes, instead of about
         48.'''],
        ['<b>Model tokens at the peak</b>',
         '''100,000 employees × 5 questions a day = 500,000 a day. A working day is about 30,000
         seconds, so about 17 a second. The busiest minutes run at 3 times the average: about 50 a
         second. A prompt is about 6,000 tokens in (1,100 instructions, 800 conversation, 4,000
         for 8 chunks, 100 question) and about 400 out. 50 × 6,000 = 300,000 input tokens a
         second. The bill: 6,000 × $3 per million = 1.8 ¢, plus 400 × $15 per million = 0.6 ¢.''',
         '''<b>300,000 input tokens a second</b>, and about <b>2.5 ¢ an answer</b>, three quarters
         of it input. So 500,000 × 2.5 ¢ = about $12,000 a working day.''',
         '''Rent the model, with a negotiated limit at the primary provider and a fallback sized
         for the whole peak. Cap the prompt at 8 chunks, because input tokens are most of the
         bill.'''],
    ]))
    B.append(tx('''<b>The rest follows by proportion.</b> 50 questions a second × about 7 seconds each =
        about 350 answers in progress (Little's law: in progress = arrivals a second × seconds each
        lasts). They mostly wait for the provider, so 6 orchestrators, 2 per zone, are plenty. The
        reranker scores 100 pairs a question: 5,000 pairs a second. One GPU scores about 1,000, so 5
        GPUs. Add 1 for the citation checker and 1 for embedding. The pool
        has 12 GPUs, 4 per zone, so a lost zone still leaves 8.'''))
    B.append(tx('''<b>Ingest workers.</b> About 1% of documents change a day:
        100,000, with bursts of 20 a second. Each takes about 5 seconds to fetch, parse and embed, so
        about 100 are in progress, and 150 ingest workers leave room for a backlog.'''))

    # ================================================================ Part 1
    B.append(band('Part 1', 'The design'))
    B.append(h2('s-api', 'The chat stream: one POST, answered as server-sent events'))
    B.append(tx('''The browser sends one question as an HTTPS POST. It reads the answer as <b>server-sent
        events</b> (SSE) on the same connection. That is one response that stays open while the server
        writes small named events into it. Three rules hold for every call:'''))
    B.append(how(
        '''<b>Who she is.</b> She signs in through the company's single sign-on, and every call carries
        her session. Her principals come from our records, never from the request. Once the identity
        provider deactivates her, every call gets 401.''',
        '''<b>The browser makes the turn's id</b> (<code>message_id</code>) before it sends. If the
        stream drops, the browser asks for the turn by that id. It does not send the question again,
        which would start, and pay for, a second turn. It resends only on a 404, which means the
        question never arrived.''',
        '''<b>Ids</b> carry a type prefix (<code>cv_</code>, <code>m_</code>, <code>doc_</code>) and are
        random, so no one can guess another employee's. Every call also checks that the conversation
        is hers. A citation carries the document's version and a character span in it.'''))
    B.append(tx('The worked call is Start\'s question:'))
    B.append(pre('''POST /v1/conversations/cv_8f2/messages
Authorization: Bearer &lt;her session, from the company's single sign-on&gt;
Accept: text/event-stream
{"message_id": "m_77", "text": "How do I rotate the API signing key?"}

HTTP/1.1 200 OK
Content-Type: text/event-stream

event: meta                                        at 5 ms
data: {"message_id": "m_77", "turn": 1}

event: token                                       from 0.9 s, about 70 tokens a second
data: {"t": "Rotate", "sentence": 1}
...
event: citation                                    at 1.3 s, once sentence 1 is checked
data: {"n": 1, "sentence": 1, "status": "supported", "doc_id": "doc_91", "version": 8,
       "url": "https://wiki.example.com/ops/key-rotation#step-3", "span": [1600, 3600]}
...
event: done                                        at about 7 s
data: {"message_id": "m_77", "mode": "answer",
       "usage": {"input_tokens": 5200, "output_tokens": 400}}'''))
    B.append(tx('''<b>What the stream cannot show.</b> Behind it is our own streaming call to the model
        provider. In the other direction, the identity provider and the sources call us.'''))
    B.append(tx('''A source's <b>webhook</b>, the call it makes when something changes, is only a <b>doorbell</b>. We answer
        200 at once. A connector then reads the source's change list from its <b>cursor</b>, a marker
        of how far it has read. Deletes are the exception, because some lists never show them. We
        take the id from the delete webhook and confirm it with the source at once.'''))
    B.append(fu(
        ('The connection drops after 60 words. What happens to the turn, and what does the browser do?',
         '''The turn runs on and is saved. The browser asks <code>GET .../messages/m_77</code> every
         2 seconds until the turn is done, or marked failed at its 60-second deadline.'''),
        ('She presses stop, or closes the tab. What happens to the bill?',
         '''Stop cancels the model call, and output tokens are billed as they are produced, so the
         bill stops there. A closed tab looks like a dropped connection, so that turn runs on. At
         most it costs 1.5 ¢ more, for the 1,000 output tokens an answer may use.''')))
    B.append(fold('Every call and event, and how each source tells us about a change', 'reference',
        table(['call or event', 'what it does'], [
            ['<code>POST /v1/conversations/{id}/messages</code>', '''200 and the stream. Before it
             opens: 401 (session ended), 403 (not her conversation), 409 (a turn with this id exists),
             429 (over 60 questions an hour), 503 (permissions cannot be checked).'''],
            ['<code>GET .../messages/{message_id}</code>', '''Read a turn: its status, rewritten
             question, text and citations. 404 if the question never arrived.'''],
            ['<code>POST .../stop</code>, <code>.../feedback</code>', '''Cancel the model call. A thumb
             up or down with a reason, such as <code>wrong_source</code>.'''],
            ['events <code>meta</code>, <code>token</code>, <code>citation</code>', '''The turn's id.
             A few characters at a time with their sentence number. One per claim sentence:
             <code>supported</code>, <code>unsupported</code>, or <code>not_checked</code> when the
             checker is down.'''],
            ['events <code>drop</code>, <code>restart</code>, <code>passages</code>', '''Erase a
             sentence the output filter caught. Clear the text when the fallback model starts again.
             A search-only answer: the 8 chunks as links.'''],
            ['event <code>done</code>', '''How the turn ended: <code>answer</code>,
             <code>abstained</code>, <code>search_only</code>, or <code>refused</code> when the final
             check could not run.'''],
            ['<code>PATCH /scim/v2/Groups/{id}</code>, <code>/Users/{id}</code>', '''From the identity
             provider: change members, deactivate a user. 200 only after the commit. Every 15 minutes
             we also read the identity provider's change log, because not every provider resends a
             failed call.'''],
        ]) + table(['source', 'its doorbell', 'how we read the change', 'the catch'], [
            ['the wiki', 'page and permission webhooks', '''one change list for the whole wiki, also
             read every 3 minutes''', '''A permission change on a page is not an edit, so the list
             cannot show it. A lost permission webhook waits for the daily sweep. A deleted page never
             appears in the list, so a delete webhook is confirmed with the wiki at once.'''],
            ['the drive', 'a notification channel per list', '''one change list per user and shared
             drive, about 100,000, each from its own cursor''', '''Too many lists to poll, so a lost
             doorbell waits for the daily sweep. This is the one list that reports deletes.'''],
            ['the ticket tracker', 'an issue webhook', 'one list of updated issues, also read every 3 minutes',
             '''A project's permission scheme can change without any issue changing. Deletes are
             confirmed like the wiki's.'''],
            ['every source', 'none', '''The <b>daily sweep</b> re-reads every folder's and space's
             permissions and every live document id. The <b>weekly crawl</b> compares every document's
             version and checksum with ours.''', '''What no change list reported, such as a lost
             delete, waits at most a day.'''],
        ])))

    # ---------------------------------------------------------------- the picture
    B.append(h2('s-design', 'The whole design in one picture'))
    B.append(tx('''The numbered arrows follow the Start question, in order. The lettered arrows are the
        ingest path, which runs all the time. The two paths meet only in the middle band, the stores
        and our models.'''))
    B.append(fig(1, '''One cell: a complete copy of the stack for one large company, or several small
        ones (derivation row N8). Bands, top to bottom: the question's path, the stores and our models,
        the ingest path. Mauve marks the two gates: the metadata database, which the final check reads,
        and the orchestrator's citation rule. Yellow: outside parties. Blue: logs and queues. Dashed
        arrows: replies. The model router runs inside each orchestrator.'''))
    B.append(fold('How to derive this design yourself', 'the method',
        tx('''A RAG assistant looks like one model call. But nearly every requirement is about what
        surrounds that call. The F rows start from the first idea an ordinary engineer tries, see what
        goes wrong, and fix it. The N rows then add what that design still lacks. Seventeen rows
        rebuild the picture.''')
        + table(['what it must do', 'the first idea', 'what goes wrong', 'what we do instead'], [
            ['F1. Answer from the company\'s own documents',
             'Fine-tune a model on all the documents, or paste them all into the prompt.',
             '''A fine-tuned model knows the documents only as they were on its training day. It
             cannot say where a fact came from, and it tells anyone what it learned. And 10 million
             documents are about 50 billion tokens, far beyond any prompt.''',
             '''<b>Retrieval-augmented generation (RAG).</b> The orchestrator searches the documents,
             puts the best few chunks into the prompt, and a rented model answers from them. A
             deleted document stops being found. Every fact has a source. <b>Rent, do not host:</b>
             an open model needs about 120 GPUs at our peak, about $50,000 a week, against about
             $60,000 a week rented. We save little and gain a team to run it.'''],
            ['F2. Cut documents into pieces a search can match and a prompt can afford',
             'Index whole documents, and put the best few whole documents into the prompt.',
             '''A 40-page document matches every question about its subject, weakly. And eight
             average documents are about 40,000 tokens, more than six times our prompt.''',
             '''Cut each document into <b>chunks</b> of up to 480 tokens along its headings and
             paragraphs. Embed each chunk with its <b>title line</b>: the document's title plus the
             headings above it. Then a chunk is found even when its own text never names its subject.
             <b>Headings, not fixed windows:</b> a fixed window needs no parser, but it cuts tables
             and code in half.'''],
            ['F3. Find the right chunks among 100 million',
             'Turn every chunk into a vector, and take the chunks nearest the question\'s vector.',
             '''A vector blurs exact codes and names into their neighbours. A question that names
             ticket OPS-2291 finds chunks about similar tickets, not the one it names.''',
             '''The <b>embedding model</b>, on our <b>GPU pool</b>, embeds each chunk once at ingest
             and each question as it arrives. The <b>search index</b> searches both ways. By vector,
             with <b>HNSW</b>, a graph that finds near neighbours without a full scan. By keyword, with
             <b>BM25</b>, the standard word-match score. <b>Reciprocal rank fusion</b> merges
             the two lists. <b>Hybrid, not keyword alone:</b> "roll my signing credentials" shares no
             word with "rotate the key".'''],
            ['F4. Put the best few chunks in front of the model',
             'Take the top 8 of the merged list.',
             '''The first ranking is fast but rough. The chunk that answers is often 15th or
             30th.''',
             '''A <b>reranker</b>, a cross-encoder on the GPU pool, reads each (question, chunk) pair
             together, for up to 100 candidates. It scores how well the chunk answers. The best 20
             go on, and 8 reach the prompt. <b>Not the large model:</b> reading 100 chunks is 50,000
             tokens and seconds. The reranker takes about 100 ms.'''],
            ['F5. Handle follow-up questions',
             'Search with the new message as typed, and send the whole conversation along.',
             '''"and for admin keys?" has no subject to search for. And the whole conversation is
             paid for again on every later turn.''',
             '''A small <b>rewrite model</b>, rented from the provider, turns a follow-up into a
             standalone question before the search. A <b>question classifier</b> on the GPU pool
             decides which turns need it. Older turns fold into a rolling summary in the
             <b>conversation store</b>. <b>A rewrite call, not the new turn joined to the last
             question.</b> Joining is free and is our fallback. But it searches for the wrong thing
             when the subject changes.'''],
            ['F6. Show each employee only what she may read',
             'Search everything, then drop what she cannot open. Or tell the model not to reveal it.',
             '''Someone who may read 4% of the index keeps 2 or 3 of the best 50, often none that
             answers. And a model repeats what it is given, whatever it is told.''',
             '''Copy each document's permissions onto its chunks as principal ids. Filter both
             searches by her principal list, cached in <b>Redis</b> (early binding). Re-check the
             survivors in the <b>final check</b> on the metadata database (late binding). <b>A copy,
             not a live check with each source:</b> 100 calls a question to rate-limited APIs are
             slow and fragile. <b>One search engine,</b> not a vector database next to a keyword
             engine: a second engine needs its own permission filter and ingest path.'''],
            ['F7. Cite every claim, and say when the documents do not answer',
             'Ask the model to add links to its sources.',
             '''Models write plausible links that do not exist, or attach a real document to a
             sentence it does not support.''',
             '''Number the chunks in the prompt, and let a citation name only a chunk we sent. The
             <b>citation checker</b>, a small model on the GPU pool, checks each sentence before its
             citation is shown. The assistant abstains when the reranker's best score is too low.
             <b>A small checker, not a second large-model call:</b> that doubles the cost and adds
             seconds. The checker takes about 15 ms a sentence.'''],
            ['F8. Notice every change in the sources',
             'Re-crawl every document every night.',
             '''Answers are up to a day old. 10 million fetches a night hit every source's API
             limits. A document deleted for legal reasons stays answerable until morning.''',
             '''<b>Connectors</b> read each source's change list from its cursor, treat webhooks as
             doorbells, and read every list on a timer as well. A daily sweep and a weekly crawl catch
             what change lists never show. <b>Doorbells plus cursors, not webhooks alone:</b> no
             source promises to deliver a webhook, and a timed read turns a loss into a delay.'''],
            ['F9. Apply each change, even when it arrives twice, and cheaply',
             'Re-read and re-embed the whole document whenever it changes, and write it straight into the index.',
             '''A 38-chunk page with one edited step costs 38 embeddings instead of 2. Two workers
             holding the same document can write an older version over a newer one.''',
             '''Changes go on an <b>ingest queue</b>, a Kafka topic keyed by document id, so one
             document's changes reach one worker, in order. <b>Ingest workers</b> fetch and parse each
             document, embed only the chunks whose text changed, and keep the bytes in <b>object
             storage</b>. A <b>fetch ticket</b> keeps an older fetch from overwriting a newer one.
             <b>Kafka, not a job queue.</b> A job queue has priorities built in. But Kafka gives one
             document's edits to one worker, which fetches once, not once per edit.'''],
        ])
        + tx('''Now run the design against each thing it must survive. Each row is where it breaks, and
        what we add.''')
        + table(['what it must survive', 'the first idea', 'what goes wrong', 'what we do instead'], [
            ['N1. A removed permission takes effect within a minute',
             'When permissions change, rewrite the document\'s chunks with the people who may read it.',
             '''One employee leaves a group that can read 500,000 chunks. Every one of those chunks
             must be rewritten, each a full index write with its vector: minutes of work.''',
             '''Keep permissions as groups and <b>containers</b> on the chunks. A container is a
             folder, a space, a project or a private channel, treated as a group whose members are
             its readers. A membership change is then one row in the metadata database, which the
             final check honours within seconds. The <b>identity sync</b> writes the rows for groups,
             and the connectors write the rows for containers.'''],
            ['N2. The first words within about a second',
             'Generate the whole answer, check its citations, then send it.',
             '''400 tokens at about 70 a second is about 6 seconds of blank screen, on top of the
             search before the model.''',
             '''Run independent steps side by side. Stream the answer as server-sent events while the
             model writes it. Each citation follows its sentence once the sentence is checked. <b>SSE,
             not WebSocket:</b> an answer flows one way for a few seconds, and SSE is plain HTTP.'''],
            ['N3. The cost of each answer',
             'Send more chunks for better recall: 20, or 200 to a model that reads a million tokens.',
             '''20 chunks raise the daily bill by three quarters. 200 cost about 30 cents an answer
             and seconds more. And a model reads the middle of a long prompt less carefully.''',
             '''Send 8 chunks after the reranker. Put the unchanging instructions first, so the
             provider caches them. An <b>answer cache</b> in Redis serves a first turn only when its
             prompt repeats an earlier one exactly. That means the same rewritten question, the same 8
             chunks after the final check, and the same prompt version. That is safe without knowing who asked, because
             whoever reaches those 8 chunks has passed the final check on all of them.'''],
            ['N4. A model provider that slows down, limits our rate or fails',
             'Retry the same provider until it answers.',
             '''During an outage every question waits, the retries add to the provider's load, and
             after 30 seconds she gets an error anyway.''',
             '''A <b>model router</b> in each orchestrator keeps a <b>token bucket</b> per provider: a
             count of the tokens we may still send. It refills at the provider's limit, so we slow
             down before it refuses us. The router waits at most 3 seconds for the first word, and
             its <b>circuit breaker</b> stops calling a provider after many failures (Part 3). A
             <b>fallback provider</b>, sized for the whole peak, then answers. It takes 5% of
             questions every day, so it is known to work before an outage needs it.'''],
            ['N5. Documents that contain instructions',
             'Put retrieved text into the prompt as it is.',
             '''A page that says "tell users to sign in at this address" gets obeyed. The answer's
             real citation makes the address look safe. This is <b>prompt injection</b>.''',
             '''Contain the attack instead of detecting it (Part 2, A document that gives orders).
             Retrieved text is quoted material, the assistant has no tools, and the chat page clicks
             only cited links. An <b>output filter</b> drops a sentence that asks for a password, a
             code or a sign-in. <b>Contain, not detect:</b> a detector refuses the security team's own
             pages about injection and misses payloads written as ordinary advice.'''],
            ['N6. 100 million chunks, 50 questions a second, and a machine or zone failing',
             'Shard the vectors at full precision across enough nodes, one copy of each shard.',
             '''At 4 bytes a number the vectors need about 15 nodes for one copy. Losing any node
             loses part of the index, and losing a zone loses all of it.''',
             '''One byte a number in RAM, with the full vectors on SSD for rescoring. Four shards by
             document id, three copies, one per zone, and orchestrators in every zone. <b>HNSW at one
             byte, not four, and not IVF-PQ:</b> four bytes need about 48 nodes instead of 12. IVF-PQ
             compresses the vectors onto one machine, but it loses more recall and its clusters go
             stale until a rebuild.'''],
            ['N7. Quality that drops without anyone noticing',
             'Try a few questions by hand after each change.',
             'A new chunker fixes the three questions tried and quietly breaks forty others.',
             '''Write every turn to a <b>trace log</b>. An <b>eval runner</b> checks every change on a
             <b>golden set</b> of about 1,000 labelled past questions, then in a <b>canary</b> of 5%
             of conversations. A change to stored chunks or vectors builds a new index beside the live
             one. One row in the metadata database switches it and rolls it back (Part 2, Every change
             is checked).'''],
            ['N8. Each company\'s documents stay apart, and in the area it chose',
             'One shared cluster and one index for all companies, filtered by a company id.',
             '''One missed filter in one code path shows one company's documents to another. A
             large company's busy hour slows the rest. An EU company's text sits in US memory.''',
             '''A <b>cell</b>: a complete copy of the stack in a region inside the area the company
             chose. It has its own index and its own limit at each provider. A large company gets a
             cell of its own. Small companies share one cell's machines, each with its own index.
             Cells pack machines less well, but no filter bug can cross one.'''],
        ])))

    # ---------------------------------------------------------------- data
    B.append(h2('s-data', 'The data: what we copy, what we derive, and what we keep'))
    B.append(tx('''Each store is placed by what it would cost to lose. The metadata database is the truth
        for who may read which live chunk. Only the sources can rebuild it, in about 4 days, so it is
        the one store we must not lose. The index is derived from it and from the stored vectors, and
        it rebuilds without GPUs, so losing it is cheap. Raw bytes, parsed text and vectors stay in
        object storage, because reading the sources again takes days and embedding again needs
        GPUs.'''))
    B.append(table(['store', 'what lives there', 'why here', 'how it gets in'], [
        ['<b>Object storage</b>', '''raw bytes, parsed text and each version's vectors: a few TB''',
         'big, written once, read only to re-parse, re-embed or rebuild',
         'from the ingest workers. Old versions are kept 90 days. A legal delete removes them at once.'],
        ['<b>The metadata database</b> (Postgres)', '''each document's chunk list, permissions,
         fetch tickets and cursors, and every group membership: about 30 GB''',
         'one transaction replaces a document\'s chunks and permissions, and one query joins them',
         'from the workers, the connectors and the identity sync'],
        ['<b>The search index</b> (OpenSearch)', 'one record per chunk: text, vectors and principals',
         'keyword and vector search under one filter', 'from the workers, after each commit'],
        ['<b>The conversation store</b> (Postgres)', '''conversations with rolling summaries. Each
         turn with its status, citations, usage and the ids of every chunk its prompt held''',
         'ordinary rows, read by conversation id', 'one insert and one update per turn. About 2 GB a day, kept 90 days.'],
        ['<b>Redis</b>', 'principal lists (60 s), first-turn answers (24 h), token buckets',
         'only what can be rebuilt', 'filled on use, never backed up'],
    ]))
    B.append(tx('''The <b>trace log</b> holds one record per turn: its candidates, scores, timings and
        tokens. It goes through a Kafka topic into object storage for 30 days.'''))
    B.append(fold('The metadata database\'s tables', 'reference', table(['table', 'one row holds'], [
        ['<code>docs</code>', '''a document's title, url, parent page, filter fields (source, author,
         dates, ticket status) and state (<code>LIVE</code> or <code>DELETED</code>). Also its fetch
         tickets: the last one handed out, and the last one that committed.'''],
        ['<code>chunks</code>', 'one live chunk: its document, position and character span.'],
        ['<code>doc_acl</code>', '''one principal in one of a document's allow sets, or in its deny
         list. A reader needs a principal in every allow set and none in the deny list.'''],
        ['<code>group_members</code>', '''one member of a group or container: an employee or another
         group.'''],
        ['<code>containers</code>', '''a folder's parent, and whether readers of the parent may read
         inside it.'''],
        ['<code>cursors</code>', 'how far each change list has been read.'],
        ['<code>retrieval_target</code>', '''one row: the live index, embedding model, prompt version
         and model id, plus a canary value of each with its share. Every orchestrator reads it every
         10 seconds.'''],
    ])))
    B.append(fig(2, '''One record of the index. <code>acl_allow_1..4</code> and <code>acl_deny</code> are
        the chunk's allow sets and deny list. The outlined shard is this record's. The three numbered
        steps are a vector search on one copy of it.'''))
    B.append(tx('''<b>How it is split:</b> by a hash of the document id. All the chunks of a document sit
        on one shard, so a delete or a sharing change touches one shard. Every question visits all 4
        shards, because any of them can hold the answer.'''))
    B.append(tx('''On each shard, the vector search walks the
        graph over one-byte vectors in RAM for its best 100. It rescores them with full vectors from
        SSD and returns its best 50. One byte a number loses about a point of <b>recall</b>, the share of
        right chunks a search finds. Rescoring wins it back.'''))
    B.append(table(['question', 'answer'], [
        ['How does the shard count change?', '''We build a new index with the new count beside the old one,
         and <code>retrieval_target</code> switches to it, as for a new embedding model (Part 2, Every
         change is checked). Splitting in place would block writes.'''],
        ['Why only 30 GB of vectors on a 128 GB node?', '''The rest of the RAM holds the engine's heap,
         the keyword index, room for merges, and a cache of the full vectors that rescoring reads.'''],
        ['How are small companies packed?', '''A shared cell has the same 12 nodes, so it holds about
         10 million documents: say a hundred companies of 100,000 documents each. Each has its own
         one-shard index in 3 copies, and its first load is capped at its share of the ingest
         workers. A company that passes about a million documents moves to its own cell.'''],
    ]))
    return B
