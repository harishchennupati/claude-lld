# Logger LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"logger/Main.java").read_text()
ext   = (H/"logger/Extensions.java").read_text()
tests = (H/"logger/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def E2(a, b):
    """slice Extensions.java between two literal markers (for a single method, not a whole ext block)"""
    i = ext.index(a)
    return ext[i:ext.index(b, i)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
# what the code must do: the hot path of one call, then the write, and the reads as a line
pf = _D
rows = [("log a line", 30, [("a call site says log.info(...)", "in a hot loop, a million times"),
                            ("is this loud enough, here?", "a short walk of volatile reads, ~3 ns"),
                            ("freeze one event", "level, who, when, thread, context"),
                            ("the whole path votes", "keep, drop, or no opinion")]),
        ("write it",    165, [("format the whole record", "outside the lock, all at once"),
                              ("take THIS sink's lock", "nothing slow is allowed inside"),
                              ("one write, count the bytes", "the count moves after the write"),
                              ("unlock, then the next sink", "or a queue, if the sink is async")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(370, 95, 370, 40, "switched off: nothing built, nothing written", "", dash=True)
pf += _ar("M815 219 V232", dash=True) + _bx(570, 232, 490, 30, "the sink threw: caught, and the next sink still gets it", "", dash=True)
pf += _tx(88, 285, "read", "var(--acc)", 13) + _tx(175, 285, "at any moment, with no restart: what level is com.shop.db at?  how deep is the queue?  how many lines have we dropped?", "var(--text)", 12, "start")
pf += _tx(615, 320, "fifty threads log at the same instant: every RECORD is whole (a stack trace is many lines and still one write), each thread's records stay in its own order,", "var(--muted)", 11.5)
pf += _tx(615, 339, "and a log call can never fail a payment", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 352, pf)

# one evening on call, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("20:10  a hot loop, DEBUG off", ["log.debug(\"cart=\" + cart), 5M times", "the gate stops it in about 3 ns",
                                        "the supplier is never called: 0 strings"], False),
      ("02:00  payments only, please", ["com.shop.payments set to DEBUG", "no restart: level is one volatile field",
                                        "children are louder on the next call"], True),
      ("02:05  a retry storm", ["400,000 identical WARNs in 90 seconds", "the rate-limit filter keeps 3 a minute",
                                "a 16-deep queue sheds 477 of 500"], True),
      ("02:30  deploy, Ctrl-C", ["close() puts a pill behind the backlog", "300 accepted, 300 written, none lost",
                                 "join(2s): no sink can hold the JVM"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 262, 100, t, lines, acc=acc)
P_EX = _mv(1230, 175, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Ask a factory for a logger by name (usually the class name) and get the same object every time; the dotted name makes a tree, and a node with no level of its own follows its nearest ancestor.</li>
<li>Six levels, and a lazy form whose message is built only if it is going to be used.</li>
<li>An exception is logged with its whole stack, causes included, and that whole block counts as one record.</li>
<li>A node may add its own sinks, and may stop using its ancestors' (additivity off).</li>
<li>Filters vote on an event independently of its level: "stop logging health checks" needs no new concept.</li>
<li>Sinks: console, file, rolling file, and a wrapper that makes any of them asynchronous.</li>
<li>Two layouts: a human-readable record, and one JSON object per line for a collector.</li>
<li>A level, a sink or a filter can change while the process is running.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>A switched-off call is a short walk of volatile reads and one compare &mdash; a few nanoseconds, and nothing allocated.</li>
<li>Concurrent writers never interleave inside one record, and each thread's records keep its own order.</li>
<li>Memory is bounded under a storm: a fixed queue that drops and counts, never an unbounded one.</li>
<li>The framework never throws into application code: a log line may not fail a payment.</li>
<li>Every lookup is O(1): a hash map for names, an integer compare for the level, copy-on-write for the sinks.</li>
<li>Layouts, sinks, filters and the clock are swappable without touching the Logger.</li>
<li>In memory, one process, one JVM (say it): shipping to a collector is a follow-up.</li></ul></div></div>
'''

PROMPT = ('"Design a logging framework &mdash; the thing behind log.info(&quot;order placed&quot;). Levels, more than '
          'one destination, configurable per package, and it must not slow down or crash the application that uses '
          'it. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Every class in an application wants to leave a trail: '
 'what happened, how serious it was, and enough around it to find the request later. A line of code calls '
 '<code>log.info("order placed")</code> and microseconds later text appears on a console, in a file, or at a '
 'collector on another machine. The people using it are two: the engineer writing the call, who wants it to cost '
 'nothing when it is switched off, and the engineer on call at two in the morning, who wants DEBUG on one package '
 'without restarting anything and without drowning in the rest. Loggers are named after packages, so '
 '<code>com.shop.db</code> follows whatever <code>com.shop</code> was set to unless it says otherwise. Many threads '
 'write to the same file at the same instant, so the one thing that must always be true is that a <i>record</i> is '
 'whole: never half of one thread\'s record with half of another\'s spliced into it, and never lost quietly. Record, '
 'not line, because an exception brings its whole stack with it &mdash; thirty physical lines that belong to one '
 'call and must land together. And one rule above all of those: the logger may never throw into the code that '
 'called it. A failed log record must not fail a payment.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that logs through a tree of loggers into more than one sink and then runs fifty threads at '
 'once. The interviewer is watching for, in this order: the questions you ask before typing (library or service, and '
 'what happens when the queue fills, are the first two); which classes exist and which one owns the level, the sinks '
 'and the file handle; one call end to end &mdash; the gate, the event, the vote, the write; what happens when fifty '
 'threads share one file; where the rules that will change (the layout, the destination, "log less") live, so each '
 'is a new class and not an edit; and what happens when the disk is full. Then the twists: rotation, structured JSON '
 'with a request id, sampling, rate limiting, per-tenant files, shipping off the box, and configuration that '
 'survives a restart.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>An in-process library, or a log service over the network?</td><td>A library; shipping is just another sink</td><td>Whether an appender is a file handle or a client (moves 1, 12)</td></tr>'
 '<tr><td>A tree of loggers by dotted name, or one flat map of names?</td><td>A tree, inheriting level and sinks</td><td>A parent pointer and a walk for the effective level (moves 1, 5)</td></tr>'
 '<tr><td>Synchronous writes, or off the caller\'s thread?</td><td>Both: async is a wrapper you switch on per sink</td><td>The decorator and its bounded queue (moves 3, 6)</td></tr>'
 '<tr><td>On a full queue: block, drop, or discard the oldest?</td><td>Drop the newest and count it; ERROR waits instead</td><td>A named policy per sink, and a metric (moves 6, 9)</td></tr>'
 '<tr><td>Must a level change take effect without a restart?</td><td>Yes</td><td><code>level</code> is a volatile field, not a config object (moves 4, 5)</td></tr>'
 '<tr><td>Which sinks for v1, and is rotation in scope?</td><td>Console and file; rotation in, shipping out</td><td>One abstract sink with the skeleton, four fillings (moves 1, 3)</td></tr>'
 '<tr><td>Structured JSON, and a request id on every line?</td><td>The layout is swappable; the context is snapshot</td><td><code>LogFormatter</code>, and the MDC copied into the event (moves 3, 6)</td></tr>'
 '<tr><td>One process and in memory, or shipped and stored?</td><td>One process; the file IS the persistence</td><td>No repository for events; a follow-up stores the config (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One night on call, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> an in-process library, not a service; loggers form a tree by dotted '
 'name and inherit level and sinks; the level gate is the first line of every call and a disabled call allocates '
 'nothing; one lock per sink, held around one write of the whole <i>record</i> &mdash; a stack trace included &mdash; '
 'with formatting outside it; a bounded queue that drops and '
 'counts rather than an unbounded one; nothing in here ever throws into the caller. Named as out of scope: rotation '
 'by time, sampling, per-tenant routing, shipping to a collector, config files &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}
# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a LOGGER named after a class asks if an EVENT is loud enough; a FORMATTER makes a line; APPENDERS write it; FILTERS vote; a FACTORY hands them out", "var(--text)", 12.5)
for x, w, t, sub, acc in [(24, 160, "Logger", "level, sinks, parent", 1), (192, 176, "LoggerContext", "the registry of names", 1),
                          (376, 176, "AbstractAppender", "a handle, a lock, a queue", 1), (560, 176, "LogEvent", "frozen facts: a record", 0),
                          (744, 186, "LogFormatter", "no state: an interface", 0), (938, 126, "LogFilter", "a vote", 0),
                          (1072, 138, "LogLevel", "a fixed list", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state that changes, so it becomes a class.   dashed = no state of its own: an interface, a value, or a fixed list", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("is this loud enough, here?", "Logger  (owns the level and the parent)", "logger.isEnabled(level)"),
                                       ("turn an event into characters", "LogFormatter  (owns nothing: pure)", "formatter.format(event)"),
                                       ("keep it, or drop it?", "LogFilter  (a counter at most)", "filter.decide(event)"),
                                       ("move the characters to a sink", "AbstractAppender  (owns the handle, the lock)", "appender.append(event)"),
                                       ("one logger per name, forever", "LoggerContext  (owns the registry)", "ctx.getLogger(name)")]):
    y = 20 + k*50
    m2 += _bx(30, y, 320, 40, verb, "the verb") + _ar("M350 %s H410" % (y+20), True)
    m2 += _bx(410, y, 420, 40, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H890" % (y+20), True)
    m2 += _bx(890, y, 310, 40, meth, "the method")
m2 += _tx(615, 292, "the one verb that touches the level, the parent chain AND the sink list is \"log this\": only the Logger sees all three, so it is the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 311, "and notice what is NOT a verb of the Logger: opening a file. A sink opens its own handle, which is why adding Kafka never edits the Logger", "var(--muted)", 11)
MV[2] = _mv(1230, 325, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 70, 230, 110, "LoggerContext", "configure(level, sinks, filters)", acc=True)
for k, (t, sub, impl) in enumerate([("LogFormatter", "text, JSON, masked", "TextFormatter / JsonFormatter / MaskingFormatter"),
                                    ("LogFilter", "deny, sample, rate-limit", "DenyMessageFilter / SamplingFilter / RateLimitFilter"),
                                    ("LogAppender", "console, file, rolling, routing", "ConsoleAppender / FileAppender / RollingFileAppender"),
                                    ("Clock", "the wall clock, or a test's", "System::currentTimeMillis, or () -&gt; t")]):
    y = 20 + k*60
    m3 += _ar("M260 125 H320 V%s H390" % (y+20), True, True) + _bx(390, y, 280, 40, t, sub, dash=True)
    m3 += _bx(740, y, 460, 40, impl, "the classes that can be handed in") + _ar("M740 %s H670" % (y+20))
m3 += _tx(615, 285, "dashed green = handed in. The Logger never builds a layout, a sink or a filter, so a JSON layout is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 304, "and one sink wraps the others: AsyncAppender(fileSink) takes ANY sink off the caller's thread without that sink being edited at all", "var(--acc)", 11)
MV[3] = _mv(1230, 318, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 210, 44, "thread A", "w.write(\"...order\")") + _bx(30, 110, 210, 44, "thread B", "w.write(\"...refund\")")
m4 += _bx(330, 70, 230, 44, "one BufferedWriter", "one file, one handle", acc=True)
m4 += _ar("M240 52 H300 V92 H330") + _ar("M240 132 H300 V92 H330")
m4 += '<rect x="600" y="20" width="330" height="145" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(765, 45, "the gap", RED, 12)
m4 += _tx(765, 68, "write() and newLine() interleave:", RED, 11) + _tx(765, 88, "09:30 INFO ord09:30 INFO refund", RED, 11)
m4 += _tx(765, 112, "and count++ is read-add-write:", RED, 11) + _tx(765, 132, "16,000 published, about 13,400 counted", RED, 11)
m4 += _tx(765, 156, "fix: the write is ONE step", "var(--text)", 11)
m4 += _bx(960, 45, 240, 95, "one lock per sink", "format outside, write inside", acc=True)
m4 += _tx(1040, 182, "the lock lives where the handle lives:", "var(--muted)", 10.5)
m4 += _tx(1040, 200, "the file and the console never wait for each other", "var(--muted)", 10.5)
m4 += _tx(615, 226, "and the unit is a RECORD, not a line: an exception is thirty physical lines in ONE string, written by ONE w.write() inside the lock,", "var(--acc)", 11)
m4 += _tx(615, 244, "so two threads throwing at the same instant can never splice their stack traces together (test 9 proves it with 8 threads x 100 exceptions)", "var(--muted)", 11)
MV[4] = _mv(1230, 258, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("which logger is this name?", "ConcurrentHashMap&lt;String, Logger&gt;", "O(1)"),
                                      ("is this level loud enough?", "an enum's int, one volatile read", "O(1), 3 ns"),
                                      ("which sinks does this node have?", "CopyOnWriteArrayList&lt;LogAppender&gt;", "O(1), no lock"),
                                      ("what is waiting to be written?", "ArrayBlockingQueue&lt;LogEvent&gt;(capacity)", "O(1), bounded"),
                                      ("how many have we dropped?", "AtomicLong", "O(1)")]):
    y = 18 + k*48
    m5 += _bx(30, y, 380, 38, q, "the question") + _ar("M410 %s H470" % (y+19), True)
    m5 += _bx(470, y, 530, 38, shape, "the shape", acc=True) + _ar("M1000 %s H1060" % (y+19), True) + _bx(1060, y, 140, 38, cost, "")
m5 += _tx(615, 275, "the one that is NOT O(1): the walk up the parent chain for the effective level, which is O(d) with d = 3 to 6 -- six volatile reads, about 3 ns", "var(--muted)", 11)
m5 += _tx(615, 294, "log4j caches that walk and pays an invalidation sweep on every setLevel; we do not, and say so out loud rather than pretending it is free", "var(--muted)", 11)
MV[5] = _mv(1230, 308, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(30, 30, 160, 44, "NEW", "no handle, no worker")
m6 += _bx(230, 30, 160, 44, "STARTED", "accepting", acc=True) + _bx(30, 120, 160, 44, "CLOSED", "drained, handle gone")
m6 += _ar("M190 52 H230", True) + _tx(210, 24, "start()", "var(--acc)", 10) + _ar("M310 74 V100 H110 V120", True) + _tx(260, 112, "close()", "var(--acc)", 10)
m6 += _tx(210, 190, "start() and close() are compare-and-set,", "var(--muted)", 10.5) + _tx(210, 208, "so a double-wired config cannot spawn two workers", "var(--muted)", 10.5)
m6 += '<rect x="430" y="20" width="780" height="196" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(820, 44, "the order inside one log call, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  the gate: one volatile read and a compare -- no event, no string, nothing allocated",
                       "2  build the event, with the thread's context COPIED in: the writer is not the caller",
                       "3  the whole path votes first, so a child's sink cannot write a line ROOT was about to veto",
                       "4  per sink: its threshold, format the WHOLE record outside the lock, then lock, ONE write, count the bytes",
                       "5  unlock, then the next sink, each inside its own try/catch",
                       "the byte count moves only after the write returned, so rotation is never ahead of the disk;",
                       "a sink that throws costs its own line and nothing else; the caller never finds out"]):
    m6 += _tx(445, 68 + k*22, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
m6 += _tx(615, 236, "three states and one rule: nothing that can fail is inside the lock, and nothing irreversible happens before the write it depends on", "var(--muted)", 11)
MV[6] = _mv(1230, 250, m6)

# move 7: what is inside the lock, and fifty callers at the same instant
m7 = _D + _card(30, 20, 560, 132, "inside the lock: about 180 nanoseconds",
                ["one write of ~75 characters into an 8 KB buffer", "one newLine()",
                 "bytesWritten += line.length() + 1, after the write", "measured, not guessed: 176 ns on this laptop"], acc=True)
m7 += _ar("M590 86 H650", True) + _tx(620, 76, "unlock", "var(--acc)", 10.5)
m7 += _card(650, 20, 550, 132, "outside the lock: nanoseconds to milliseconds",
            ["the gate: 3 ns.  the event plus the format: ~250 ns", "the flush at ERROR: a real system call",
             "the disk, when the buffer fills: milliseconds", "the collector, for a shipping sink: tens of ms"])
m7 += _tx(615, 180, "fifty threads log into ONE file sink at the same instant", "var(--text)", 12)
for k, n in enumerate([1, 6, 11, 16, 21, 26, 31, 36, 41, 50]):
    x = 30 + k*118
    m7 += _bx(x, 195, 106, 40, "thread %d" % n, "waits %s" % ("0" if n == 1 else "%.1f us" % ((n-1)*0.18)), acc=(k == 9))
m7 += _tx(615, 263, "the fiftieth thread waits about nine microseconds for the lock, then returns; put the async wrapper in front and it waits 1.6 microseconds", "var(--muted)", 11)
m7 += _tx(615, 282, "for a queue slot and returns before a single character has been written. One at a time is true, and at 180 nanoseconds nobody can tell.", "var(--muted)", 11)
MV[7] = _mv(1230, 296, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="570" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(305, 42, "one lock per sink: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of one line: one buffered write, about 180 ns",
                       "a service at 5,000 requests a second, 4 lines each: 20,000 a second",
                       "20,000 x 180 ns = 3.6 ms of lock in every second: 0.36% busy",
                       "even 200,000 lines a second is 36 ms in a second: 3.6% busy",
                       "and the lock is per SINK, so the file and the console never meet"]):
    m8 += _tx(35, 68 + k*25, l, "var(--muted)", 11, "start")
m8 += _tx(900, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  format outside the lock, flush only at ERROR", "already done: the lock is 180 ns, not the 430 ns whole call"),
                              ("2  wrap the sink in AsyncAppender", "the caller pays one ~33 ns enqueue and stops paying format AND write"),
                              ("3  one sink per hot subsystem, then off the box", "the sink becomes a client: batch, ship, and a file is not your problem")]):
    m8 += _bx(610, 58 + k*52, 590, 44, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 224, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two threads splice a line, or a stack trace", "one lock per sink around the whole record; tests 1 and 9: 1,000 lines, then 800 intact traces"),
                                ("log.debug(\"cart=\" + cart) with DEBUG off", "the gate first, plus a Supplier form; test 2: 1,000 disabled calls, the supplier ran 0 times"),
                                ("a storm fills memory and the JVM dies", "a fixed queue that drops and counts; test 5: written + dropped = offered, peak depth 16 of 16"),
                                ("the disk is full, or the collector is down", "caught in the sink and reported on stderr; tests 6 and 12: a broken sink, filter and collector"),
                                ("Ctrl-C and the async tail is gone", "a poison pill behind the backlog, join(2s); test 8: 300 accepted, 300 written"),
                                ("a pooled thread leaks the last request's id", "the context is COPIED into the event; tests 8 and 13: every line still says rid=req-A")]):
    y = 18 + k*42
    m9 += _bx(30, y, 340, 38, bad, "") + _ar("M370 %s H420" % (y+19), True) + _bx(420, y, 780, 38, fix, "", acc=True)
m9 += _tx(615, 292, "every claim this design makes has a test, the twists on page 05 included: FailureTests.java runs fifty-eight of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 305, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface LogFormatter { String format(LogEvent e); }", None), ("a JSON layout is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new AsyncAppender(\"async\", fileSink, 8192, BLOCK, ERROR)", None), ("any sink goes off-thread untouched", None)],
          [("Template Method", "var(--text)"), ("move 6", None), ("AbstractAppender.append is FINAL; only write() is open", None), ("no sink can skip the lock or throw", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("logger.addAppender(a) -- the sinks ARE the listeners", None), ("the logger never knows what a file is", None)],
          [("Chain of Responsibility", "var(--text)"), ("move 3", None), ("the filter chain: the first opinionated vote wins", None), ("\"log less\" never touches the Logger", None)],
          [("State", "var(--text)"), ("move 6", None), ("NEW &rarr; STARTED &rarr; CLOSED, by compareAndSet", None), ("a double-wired config starts one worker", None)],
          [("Factory", "var(--text)"), ("move 2", None), ("ctx.getLogger(name): one object per name, forever", None), ("a level change reaches every static field", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("the context is handed to its callers; no getInstance()", "var(--muted)"), ("a test builds a fresh LoggerContext", "var(--muted)")],
          [("Builder", "var(--muted)"), ("not yet", None), ("a sink has four constructor arguments and all are required", "var(--muted)"), ("it earns a place when a config file arrives", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 335, "name a pattern only after the move that produced it; then every name has a one-sentence defence. Factory is the one that DID earn it here: identity is the requirement.", "var(--muted)", 11)
MV[10] = _mv(1230, 350, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("an event carries facts, a formatter makes characters, a sink moves them, the Logger routes", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("RateLimitFilter arrived mid-round: Logger, every sink and every formatter were untouched", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("addAppender(a): console, file, rolling, async, routing; append() is final, so none can lie", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each where possible", None), ("move 3", None), ("LogFormatter, LogFilter, Clock: one method each; queueDepth() is on AsyncAppender only", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("ctx.configure(INFO, List.of(console), List.of(filter));  ctx.setClock(() -&gt; t)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "sample, rate-limit, mask, redact", "a new class behind LogFilter or LogFormatter, plus one wiring line", "", "move 3"),
        ("someone new wants to know", "a collector, a pager, a metric", "one more appender on the node; the Logger does not change", "", "move 3"),
        ("a new step in a life", "PAUSED while a disk recovers", "one more appender state and one more checked transition", "", "move 6"),
        ("a new invariant across items", "roll the file at 100 MB", "the check, the handle swap and the write inside the SAME lock", "", "move 4"),
        ("state that must outlive the process", "the level tree; shipping off the box", "the levels behind a LevelStore; the shipper clears its buffer only", "after the send returned, and the batch id makes a retry harmless", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the Logger, the event and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>logger</b> named after a class decides whether an <b>event</b> is loud enough; a "
 "<b>formatter</b> turns it into a line; <b>appenders</b> write it somewhere; <b>filters</b> vote on it; a "
 "<b>factory</b> hands out the loggers. A logger has a level, a parent, a list of sinks and a list of filters, all of "
 "which change while the process runs: a class. An appender has a file handle, a lock, sometimes a queue and a "
 "worker thread: a class. The context has the registry of names: a class. An event is the opposite &mdash; it is "
 "born, read and thrown away, and it is read by a thread that did not create it, so it is a <i>record</i>, frozen at "
 "creation, including a copy of the thread's context map. A formatter has no state at all, so it is an interface. A "
 "filter has a counter at most. And a level is not a class per level: it is a fixed list with a number attached, "
 "which is an enum, because the only thing anybody ever does with a level is compare it.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "The table above is the whole move; two rows in it are worth saying out loud. The first: \"turn an event into "
 "characters\" and \"keep it or drop it\" touch <i>nothing</i> &mdash; one immutable input, one answer out &mdash; "
 "which is what makes them pure rules that can be handed in rather than methods on anybody. The second: the one verb "
 "that touches the level, the parent chain <i>and</i> the sink list at the same time is \"log this\", and only the "
 "logger sees all three, so the logger is the orchestrator and nothing else is. Then notice what is <i>not</i> a verb "
 "of the logger: opening a file. A sink opens its own handle, which is exactly why adding a Kafka sink next year does "
 "not open the Logger class.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "What text a line becomes will change: a sentence today, JSON tomorrow, masked the day after. Where it goes will "
 "change: a console today, a rolling file in staging, a collector in production. What gets dropped will change: "
 "health checks today, one-in-a-hundred DEBUG next week, a cap on a repeated line at two in the morning. Each becomes "
 "a one-method interface the context is <i>given</i> in <code>configure()</code> and never builds. This is where the "
 "patterns come from, not the other way round: a swappable rule behind an interface is <b>Strategy</b>; the filter "
 "chain where the first opinionated vote wins is <b>Chain of Responsibility</b>; a logger that announces an event "
 "without knowing what a file is, is <b>Observer</b> &mdash; the appenders <i>are</i> the observers. And the one that "
 "matters most here is <b>Decorator</b>: <code>AsyncAppender</code> holds any other sink and takes it off the "
 "caller's thread without that sink being edited at all, which is how \"never let a slow disk stall checkout\" costs "
 "one wiring line. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Two threads call <code>write()</code> and <code>newLine()</code> on the same <code>BufferedWriter</code>. Those are "
 "two calls, not one, so the characters interleave and the file gets half of one line spliced into another: "
 "<code>09:30 INFO ord09:30 INFO refund</code>. The same gap eats counters, because <code>count++</code> is a read, "
 "an add and a write &mdash; the demo publishes sixteen thousand events into an unlocked counting sink and it reports "
 "about thirteen thousand of them. So the write must be one step, owned by the thing that owns the handle: the "
 "appender. The lock is per <i>sink</i>, not per framework, which is the whole trick &mdash; the file and the console "
 "and the collector never wait for each other, and neither do two files. And what is inside that lock is the "
 "narrowest thing possible: not the formatting, which is pure arithmetic over an immutable event and runs before the "
 "lock is taken. Say the unit out loud, because the interviewer will push on it: the thing that must be whole is a "
 "<b>record</b>, not a line. A logged exception is its message plus thirty frames of stack, and the formatter returns "
 "all of that as <i>one string</i> so the sink writes it with one <code>write()</code> inside one lock; eight threads "
 "each throwing a hundred times produce eight hundred intact blocks and never a frame from one thread inside "
 "another's trace.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "Three of those choices are worth defending out loud. <code>CopyOnWriteArrayList</code> for the sinks, because "
 "reconfiguration happens a handful of times in a process and dispatch happens millions of times a second: you pay "
 "the copy on the rare side and every log call iterates a snapshot with no lock at all. <code>ArrayBlockingQueue</code> "
 "with a capacity, because the capacity <i>is</i> the memory bound &mdash; there is no other back-pressure in the "
 "design. And the honest one: the walk up the parent chain for the effective level is <i>not</i> O(1). It is O(d) "
 "with a depth of three to six, so a handful of volatile reads, single-digit nanoseconds. Log4j caches that walk and "
 "pays an invalidation sweep on every <code>setLevel</code>; this does not, and says so rather than pretending.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "An appender is NEW until <code>start()</code>, STARTED while it accepts, CLOSED after it drains. Both transitions "
 "are compare-and-set, so a config wired twice cannot spawn two worker threads on one handle. Writing the states "
 "down forces the question the interviewer will ask: what is the order inside one call? First the gate &mdash; one "
 "volatile read and a compare, with nothing allocated, which is what makes a switched-off call free. Then the event, "
 "with the thread's context <i>copied</i> into it, because with an async sink the thread that writes the line is not "
 "the thread that made it. Then the whole path votes, so a child's sink cannot write a line ROOT was about to veto. "
 "Only then, per sink: its own threshold, the formatting <i>outside</i> the lock &mdash; and rendering a stack trace "
 "is the one genuinely expensive piece of formatting, microseconds rather than nanoseconds, which is exactly why it "
 "must not be inside &mdash; the lock, one write, and the byte "
 "counter moved <i>after</i> the write returned &mdash; so a failed write leaves the count where it was and rotation "
 "is never ahead of the disk. Then unlock, then the next sink, each inside its own try/catch. And <code>close()</code> "
 "puts a poison pill <i>behind</i> the backlog, so everything already accepted is written, in order, before the "
 "process ends.", 6),
("Move 7: yes, the lock makes one sink's lines happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every record takes the sink's lock, has logging become "
 "a queue? It has, for about a hundred and eighty nanoseconds &mdash; that is one buffered write of seventy-five "
 "characters, one newline, and one addition to the byte counter, measured rather than guessed. Everything slow is "
 "outside it: the gate at three nanoseconds, building the event and the line at about two hundred and fifty, the "
 "flush at ERROR which is a real system call, the disk when the buffer fills, and the collector at tens of "
 "milliseconds for a shipping sink. So when fifty threads log into one file at the same instant, the fiftieth waits "
 "about nine microseconds and then returns. Put the async wrapper in front and the fiftieth waits one and a half "
 "microseconds for a queue slot and returns before a single character has been written.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A service handling five thousand requests a second with four lines each produces twenty thousand events a second. "
 "At a hundred and eighty nanoseconds of lock per line that is three and a half milliseconds of lock in every "
 "second: busy roughly a third of one per cent. Even a fictional service at two hundred thousand lines a second is "
 "only three and a half per cent, and the lock is per sink, so the file and the console are not the same queue. Then "
 "the ladder, in the order you would climb it: keep formatting outside the lock and flush only at ERROR, which this "
 "code already does and which is the difference between a hundred and eighty nanoseconds and the four hundred and "
 "thirty a whole call costs; wrap the sink in <code>AsyncAppender</code>, which leaves the caller paying a "
 "thirty-three nanosecond enqueue and nothing else &mdash; the formatting moves to the worker along with the write "
 "&mdash; and lets that one worker batch sixty-four events per lock acquisition; and beyond that, give each hot "
 "subsystem its own sink and then move off the box entirely, where the sink becomes a client that batches and ships "
 "and a file is somebody else's problem. Say the arithmetic first: climbing the ladder without it is complexity "
 "nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Two threads writing half a record each into one file (one lock per sink, and two tests: fifty threads write a "
 "thousand lines and every one comes back whole and in its own thread's order, then eight threads throw a hundred "
 "exceptions each and all eight hundred stack traces come back unspliced). A message built for a level that is "
 "switched off (the gate first, plus a <code>Supplier</code> form, and a test that makes a thousand disabled calls "
 "and asserts the supplier ran zero times). A storm that fills memory (a fixed queue, and a test that asserts written "
 "plus dropped equals offered and that the depth peaked at sixteen of sixteen). A full disk or a dead collector "
 "(caught inside the sink and reported on stderr, and a test with a broken sink, a broken filter, a broken formatter, "
 "a broken supplier and a collector that never comes back, all of which cost only their own record). Ctrl-C during a "
 "deploy (a poison pill behind the backlog, and a test that accepts three hundred lines and finds three hundred "
 "written). A pooled thread carrying the last request's id (the context copied into the event, and a test that "
 "changes the thread's context after the call and finds the old value on the line). Fifty-eight checks &mdash; the "
 "twists on page 05 have their own, because an untested twist is a claim &mdash; and they all run in about a second.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Read the second column first: every name in that table is the <i>output</i> of a move, which is why each has a "
 "one-sentence defence and why none of them was decided before the code existed. The load-bearing one is Decorator, "
 "because it is what made two hard requirements cheap: <code>AsyncAppender</code> holds any sink and takes it off the "
 "caller's thread, <code>MaskingFormatter</code> holds any layout and redacts what it produced, and neither of the "
 "things being wrapped was edited. The one that matters second is Template Method, because it is enforcement rather "
 "than style: <code>AbstractAppender.append</code> is <code>final</code>, so a sink author physically cannot forget "
 "the lock or leak an exception, and the only hole left is <code>write()</code>, which runs with the lock already "
 "held. The two that earned nothing are on the table too, greyed out, with the reason; say those out loud as well, "
 "because refusing a pattern is worth as much as naming one.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the answer; this is only what it could not fit. O is true here as a fact rather than an intention: "
 "<code>RateLimitFilter</code> was written after everything else and cost one class and one wiring line &mdash; no "
 "appender, no formatter and not one line of <code>Logger</code> moved. L is true because <code>append()</code> is "
 "<code>final</code>: a subclass physically cannot skip the lock or leak an exception, so \"any implementation drops "
 "in\" is enforced, not hoped for. I survives even the stack trace, because the renderer is a <i>static</i> helper on "
 "<code>LogFormatter</code> rather than a second method every layout would have to implement, so a formatter is still "
 "a lambda. And D pays off in the tests more than in the design: nothing news up a collaborator, so a test can hand "
 "the tree a clock that says last Tuesday and assert the exact timestamp on the line.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Two of the five rows need a sentence the picture cannot hold. \"A new invariant across items\" is rotation, and "
 "the whole trick is that the size check, the handle swap and the write happen inside the <i>same</i> lock &mdash; "
 "that is why a record is never split across two files. \"State that must outlive the process\" is really two "
 "questions: the log file already <i>is</i> the persistence for events, so what is left is the level tree behind a "
 "<code>LevelStore</code> repository and the shipping sink, which clears its buffer only after the send returned and "
 "stamps each batch with an id so a repeat is applied once at the far side. For all five the Logger, the event and "
 "the tests do not change; that is the test that the derivation was right, and page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, the "
 "patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is named "
 "before the move that produced it. On this problem two moves carry more weight than usual: move 4, because the shared "
 "thing is a file handle and the damage is a torn line rather than a wrong number, and move 6, because the order inside "
 "one call is the entire performance story.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the values, the time, the framework's own error channel, and the wiring
put("mdc", 10, 20, 240, "Mdc", ["CTX: ThreadLocal&lt;Map&gt;"],
    ["put / remove / clear", "snapshot(): an unmodifiable copy"])
put("event", 10, 135, 240, "LogEvent", ["tsMs, level, loggerName", "threadName, message", "error: Throwable",
                                        "context: Map (a snapshot)"], [], "record")
put("clock", 10, 265, 240, "Clock", [], ["nowMs(): long"], "interface")
put("status", 10, 345, 240, "Status", ["errors: AtomicLong", "sink: PrintStream"],
    ["error(what, t)", "errorCount(): long"])
put("wire", 10, 480, 240, "main()", [], ["builds the sinks", "ctx.configure(...)", "the ONLY place the", "concrete graph is named"])
# centre column: the registry, the node, and the skeleton every sink fills
put("ctx", 290, 20, 345, "LoggerContext",
    ["registry: ConcurrentHashMap", "root: Logger  (always has a level)", "clock: Clock"],
    ["getLogger(name) / getLogger(Class)", "configure(level, sinks, filters)", "setClock(c) / names()", "shutdown(): closes each sink once"])
put("logger", 290, 215, 345, "Logger",
    ["name: String", "parent: Logger  (null at ROOT)", "level: volatile  (null = inherit)", "additive: volatile boolean",
     "appenders: CopyOnWriteArrayList", "filters: CopyOnWriteArrayList"],
    ["trace/debug/info/warn/error/fatal", "debug(Supplier) / info(Supplier)", "isEnabled(lv) / effectiveLevel()",
     "addAppender(a) / addFilter(f)", "setLevel(lv) / setAdditive(b)", "log(lv, msg, err) &rarr; emit(...)"])
put("abs", 290, 480, 345, "AbstractAppender",
    ["formatter: volatile LogFormatter", "threshold: volatile LogLevel", "lock: ReentrantLock", "started: AtomicBoolean"],
    ["append(e)  FINAL: threshold,", "   format, lock, write, unlock", "write(e, line)  abstract, lock held",
     "start() / close()  once, by CAS"], abstract=True)
# third column: the enums, the filter seam and the formatter seam
put("level", 672, 20, 240, "LogLevel", ["TRACE 10, DEBUG 20, INFO 30", "WARN 40, ERROR 50, FATAL 60", "OFF  the sentinel"],
    ["atLeast(bar): boolean"], "enum")
put("fdec", 672, 148, 240, "FilterDecision", ["ACCEPT, DENY, NEUTRAL"], [], "enum")
put("filter", 672, 220, 240, "LogFilter", [], ["decide(e): FilterDecision"], "interface")
put("deny", 672, 298, 240, "DenyMessageFilter", [], ["DENY on a substring", "(sampling, rate limit: p05)"])
put("fmt", 672, 400, 240, "LogFormatter", [], ["format(e): String", "stackOf(t): String  static"], "interface")
put("text", 672, 490, 240, "TextFormatter", [], ["one record: a line,", "then the stack under it"])
put("json", 672, 592, 240, "JsonFormatter", [], ["one flat JSON object", "stack as an escaped field"])
# fourth column: the appender seam, the decorator, and the sinks that exist to prove the claims
put("appi", 960, 20, 250, "LogAppender", [], ["name() / append(e)", "start() / close()"], "interface")
put("async", 960, 150, 250, "AsyncAppender",
    ["delegate: LogAppender", "queue: ArrayBlockingQueue", "policy: OverflowPolicy", "worker: daemon Thread", "dropped: AtomicLong"],
    ["append &rarr; offer, or the policy", "close &rarr; pill, then join(2s)", "droppedCount / queueDepth"])
put("policy", 960, 360, 250, "OverflowPolicy", ["DROP_NEWEST", "DISCARD_OLDEST", "BLOCK"], [], "enum")
put("unsafe", 960, 470, 250, "UnsafeCountingAppender", [], ["count++ with NO lock", "loses thousands of 16,000"])
put("safe", 960, 560, 250, "SafeCountingAppender", [], ["count++ under the lock", "exact, every time"])
put("slow", 960, 650, 250, "SlowAppender", [], ["sleeps with the lock held", "so a queue really fills"])
# the bottom row: the four concrete sinks, on one inheritance bus
put("console", 30, 740, 215, "ConsoleAppender", [], ["out.println(line)"])
put("memory", 270, 740, 215, "MemoryAppender", [], ["lines(): List (for tests)"])
put("file", 510, 740, 225, "FileAppender", ["writer: BufferedWriter", "bytesWritten: long"], ["count AFTER the write"])
put("roll", 760, 740, 260, "RollingFileAppender", ["maxBytes: long"], ["roll inside the same lock"])

def stub(x, y1, y2):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x, y1, x, y2)
def hbus(x1, x2, y):
    return '<path d="M%s %s H%s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2)

EDGES = [
 # the four concrete sinks sit on one bus that runs up into AbstractAppender
 hbus(137, 622, 712), stub(137, 740, 712), stub(377, 740, 712), stub(622, 740, 712),
 ln((462, 712), B["abs"]["b"], "inherit"),
 ln(B["roll"]["l"], B["file"]["r"], "inherit"),
 # AbstractAppender and AsyncAppender both implement LogAppender
 ln(B["abs"]["r"], B["appi"]["l"], "inherit", "", [(925, 565), (925, 55)]),
 ln((985, 150), (985, 90), "inherit"),
 ln((1185, 150), (1185, 90), "assoc"),
 _tx(1085, 124, "implements it, and wraps one", "var(--acc)", 10),
 ln(B["async"]["b"], B["policy"]["t"], "assoc"),
 # the concrete filters and formatters
 ln(B["deny"]["t"], B["filter"]["b"], "inherit"),
 ln(B["text"]["t"], B["fmt"]["b"], "inherit"),
 ln(B["json"]["r"], B["fmt"]["r"], "inherit", "", [(928, 627), (928, 435)]),
 # the context owns the loggers; a logger points at its parent
 ln(B["logger"]["t"], B["ctx"]["b"], "compose", "one per name"),
 ln((635, 296), (635, 278), "assoc", "", [(656, 296), (656, 278)]),
 _tx(672, 291, "parent", "var(--muted)", 10, "start"),
 # the logger holds its sinks and its filters, and reads its level
 ln((635, 385), B["appi"]["b"], "assoc", "", [(945, 385), (945, 110), (1085, 110)]),
 _tx(643, 381, "its own sinks", "var(--muted)", 10, "start"),
 ln((635, 250), B["filter"]["l"], "assoc"),
 ln((635, 228), B["level"]["l"], "assoc"),
 # a sink is handed a layout, and reports its own failures on the status channel
 ln((635, 520), B["fmt"]["l"], "inject"),
 ln(B["abs"]["l"], B["status"]["r"], "assoc"),
 # the logger builds the event; the event carries a copy of the thread's context
 ln(B["logger"]["l"], B["event"]["r"], "assoc"),
 ln(B["event"]["t"], B["mdc"]["b"], "assoc", "a copy"),
 # time is handed in; main() is the only place the graph is named
 ln((290, 110), B["clock"]["r"], "inject", "", [(266, 110), (266, 292)]),
 ln(B["wire"]["t"], B["ctx"]["l"], "inject", "configure()", [(130, 462), (280, 462), (280, 101)]),
]
UMLSVG = uml_svg(1230, 875, EDGES, legend_y=855)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (italic = abstract, dashed border = interface, '
 '&laquo;enum&raquo; = a fixed list of values, &laquo;record&raquo; = frozen fields). Middle: its fields, the state it '
 'holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = extends or implements: four concrete sinks fill one '
 'skeleton, and <code>AsyncAppender</code> implements the interface directly because it formats nothing and owns no '
 'handle, which is what lets it wrap any of the others. Filled diamond = owns: the context owns one logger per name. '
 'Plain arrow = references. Dashed green = handed in, never built here. <b>Where state lives:</b> a logger has the '
 'level, the parent pointer, its own sinks and its own filters &mdash; and nothing else; an appender has the handle, '
 'the lock, and for the async one the queue, the worker and the dropped counter; an event has frozen facts including a '
 '<i>copy</i> of the thread\'s context, which is what makes it safe to hand to a worker thread. Notice what is '
 '<i>not</i> here: no Level class per level, because the only thing anybody does with a level is compare it; and no '
 'buffer inside the Logger, because the thing that queues is a sink, so it can be switched on for one destination and '
 'not another.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (fifty-eight checks, including one per twist; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (library or service, and what happens when the queue '
 'fills, first); then type in the order of Main.java: the LogLevel enum, the Clock, the Mdc, the LogEvent record, the '
 'LogFormatter interface with a text and a JSON layout, FilterDecision and LogFilter, the LogAppender interface, '
 'AbstractAppender with its final append() and the lock, the console and file sinks, OverflowPolicy and AsyncAppender, '
 'Status, then Logger with the gate and the two passes, then LoggerContext with the registry, then a main with fifty '
 'threads.</div></div>')

FU = [
("At two in the morning: turn DEBUG on for the payments package only, without restarting anything.", "functional", 8,
 "Loggers are a tree built from the dotted name, so setting the level on com.shop.payments turns on every logger "
 "under it and nothing else. A node's own level is nullable and null means inherit, so effectiveLevel() walks up "
 "until somebody has an opinion, and ROOT always does. The field is volatile rather than locked: one writer at 2am, "
 "millions of readers on the hot path, and readers need visibility rather than atomicity, so the change is seen on "
 "the very next call with no restart and no lock. A child that has set its own level keeps it, which is how you turn "
 "one noisy subtree down while turning its parent up. The other half of \"configurable per package\" is <i>where</i> "
 "the lines go: a node writes to its own sinks and then walks up to its ancestors' as well, unless "
 "<code>setAdditive(false)</code> stops the walk &mdash; which is how one subtree gets its own file while everything "
 "else keeps the shared console, or leaves the shared console entirely.",
 sect(src, "private volatile LogLevel level;", "/** When false, events stop here")
 + "\n" + sect(src, "LogLevel effectiveLevel()", "/** TRACE with a plain message. */")
 + "\n" + sect(src, "Logger getLogger(String name)", "/** The usual call site")),
("Fifty threads log to one file at the same instant. Prove no line is torn and none is lost, with a test.", "non-functional", 10,
 "The damage a race does here is not a wrong number, it is a wrong line: write() and newLine() are two calls, so two "
 "threads interleave into half-lines. One ReentrantLock per sink, taken around the write and nothing else, makes "
 "them one step. The proof is a test rather than an argument: fifty real threads (a pool of fifty, not a pool of "
 "sixteen taking turns) wait on one latch, each writes twenty lines through an async sink onto one file, and the test "
 "then reads the file back and asserts five things &mdash; a thousand lines arrived, every one matches the whole-line "
 "pattern, each thread's own sequence numbers are in increasing order, no line appears twice, and the dropped counter "
 "is zero. Say the limit of the guarantee out loud, because it is the follow-up: the lock is per sink <i>object</i>, "
 "so two FileAppenders opened on the same path are two locks and would tear each other's lines. One destination means "
 "one sink object, shared by every logger that writes there.",
 T("        // 1. fifty threads log to ONE file", "        // 2. the gate is first")),
("One lock per sink. Have you just serialised the whole application behind a log call?", "non-functional", 5,
 "No, and the answer is arithmetic rather than opinion. Everything inside the lock is on the screen below: one "
 "buffered write of about seventy-five characters, one newline, a flush only at ERROR, and one addition &mdash; about a "
 "hundred and eighty nanoseconds. A service at five thousand requests a second with four lines each is twenty "
 "thousand events a second, so three and a half milliseconds of lock in every second: about a third of one per cent. "
 "Even two hundred thousand lines a second is three and a half per cent, and the lock is per sink, so the file and "
 "the console are not the same queue. The ladder, in order: format outside the lock and flush only at ERROR, which is "
 "already done; wrap the sink in AsyncAppender, which leaves the caller paying one thirty-three nanosecond enqueue "
 "and lets one worker batch sixty-four records per lock acquisition; then a sink per hot subsystem, and past that the "
 "sink becomes a network client.",
 sect(src, "protected void write(LogEvent e, String line) throws IOException {\n        BufferedWriter w = writer;", "/** How many characters are in the current file.")),
("Why not just call System.out.println? Show me what the logger is buying.", "non-functional", 3,
 "Two costs, and both are measurable. The first is a lock you do not control: PrintStream synchronises on itself, so "
 "every println in the process queues behind every other one, including the ones in libraries you did not write. The "
 "second is bigger: the console stream is autoflush, so every line is its own system call. The extension writes "
 "twenty thousand identical lines both ways and the numbers on this laptop are about 110 ms with a flush per line "
 "against about 25 ms through one 64 KB buffer &mdash; roughly five times, for the same bytes. That is why the file "
 "sink buffers and flushes only at ERROR and above, where you would rather lose the throughput than the last line "
 "before a crash, and why a console sink is a sink like any other rather than the default.",
 X("why System.out is slow", "Runs every extension")),
("The disk is full and the sink throws. What happens to the checkout that logged the line?", "non-functional", 5,
 "Nothing. The write sits inside a try/catch in AbstractAppender.append, which is final precisely so that no sink "
 "author can remove it, and the failure is reported on the framework's own channel &mdash; a Status class that "
 "writes to stderr, because logging your own failure through yourself is a loop. The event then goes to the next "
 "sink on the path, each inside its own try/catch in the Logger, so one dead collector does not cost you the file. "
 "The same guard covers a formatter that throws and a message supplier that throws. The failure test wires a sink "
 "that always throws, a filter that always throws, a formatter that always throws and a supplier that throws, and "
 "checks that the surviving sink still got its lines and that the caller never saw an exception.",
 sect(src, "public final void append(LogEvent e)", "/** Move the characters.")
 + "\n" + sect(src, "final class Status", "final class Logger {")),
("log.debug(\"cart=\" + cart) sits in a hot loop with DEBUG switched off. What does it cost?", "non-functional", 5,
 "Written that way it costs the whole string concatenation, every time, because Java builds the argument before the "
 "call. The framework's half of the fix is that the gate is the first line of log(): one volatile read per node up "
 "to ROOT and an integer compare, about three nanoseconds for a depth of six, with no event allocated and no string "
 "built. The caller's half is the lazy form, debug(Supplier), where the supplier is only invoked after the gate "
 "passes. The test makes a thousand disabled calls with a counting supplier and asserts it ran zero times, then one "
 "enabled call and asserts it ran exactly once.",
 sect(src, "/** The gate. Three to five volatile reads", "/** ERROR with a plain message. */")
 + "\n" + sect(src, "/** The gate first, then the work.", "/**\n     * Two passes on purpose.")),
("Checkout must never wait on an fsync. Take the write off the caller's thread — and tell me what happens when the queue fills.", "twist", 10,
 "AsyncAppender is a decorator: it holds any other sink, puts events on an ArrayBlockingQueue and lets one daemon "
 "worker drain them, so the caller's whole cost is an offer at about thirty-three nanoseconds. Bounded is the point: "
 "unbounded turns a storm into an OutOfMemoryError and blocking turns a slow disk into slow checkouts. When the "
 "queue is full a named policy decides &mdash; drop the newest and count it, discard the oldest to keep the freshest "
 "picture, or block &mdash; and it is a per-sink choice, not a framework law, so an audit sink is built with BLOCK "
 "while everything else sheds. ERROR and above get one bounded wait before they are given up on. The worker drains "
 "sixty-four at a time, which turns sixty-four lock acquisitions into one. The test offers five hundred events into a "
 "sixteen-deep queue in front of a two-millisecond sink and asserts the only arithmetic that matters: written plus "
 "dropped equals offered. Shedding is fine; shedding silently is not.",
 sect(src, "enum OverflowPolicy", "final class Status")),
("We deploy with Ctrl-C. What happens to the lines still in the queue?", "non-functional", 5,
 "close() is the whole answer and it is four steps in one order. A compare-and-set makes it happen once, however many "
 "loggers share this sink. The accepting flag goes false, so nothing new joins the backlog. Then the poison pill is "
 "offered <i>behind</i> everything already queued, which is what makes the drain finish in order instead of stopping "
 "wherever it happens to be. Then join(2000): the worker is a daemon and the wait is bounded, so a wedged sink delays "
 "a deploy by two seconds and never holds the JVM open. LoggerContext.shutdown() walks the tree and closes each sink "
 "exactly once, deduped by identity because one async sink is usually on several nodes, and Configurator."
 "installShutdownHook is the one line in main that makes Ctrl-C run all of it. The honest gap to say before they ask: "
 "a thread already past the accepting check can still lose its event, and closing that window needs a lock on every "
 "append &mdash; right for an audit sink, wrong for checkout. The test accepts three hundred lines, closes, and finds "
 "three hundred written; the line offered after close is counted on the dropped counter, never half-written.",
 sect(src, "    public void close() {\n        if (!started.compareAndSet(true, false)) return;\n        accepting = false;", "/** Events given up on")
 + "\n" + sect(src, "void shutdown() {", "}\n\n/** The demo: the tree")
 + "\n" + E2("    /** Ctrl-C must not lose the async tail.", "}\n\n// ---- ext: why System.out is slow")),
("Roll the file at 100 MB. Then at midnight. Then one file per tenant.", "twist", 8,
 "All three are the same move in three places. Size rolling lives in Main: RollingFileAppender extends FileAppender "
 "and overrides write(), which already runs under the sink's lock, so the size check, the handle swap and the write "
 "are one step and a line is never split across two files; the base class already counts bytes, and it counts them "
 "after the write returns, so the number is never ahead of the disk. Time rolling is the same override keyed on "
 "clock.nowMs() / periodMs instead of a byte count, which is why a test can roll three days in a microsecond. "
 "Per-tenant is a sink that picks a sink: RoutingAppender reads a key off the event's context and forwards to a "
 "delegate built lazily for that key, with a cap, because keys that come from request data are user input and an "
 "uncapped map of sinks is a file-handle leak with a pretty name.",
 sect(src, "final class RollingFileAppender", "/** A sink that keeps the lines in memory.")
 + "\n" + X("roll at midnight", "one file per tenant")),
("Ship structured JSON to a collector, with the request id on every line.", "twist", 8,
 "Two seams, both already there. The layout is a Strategy, so JsonFormatter is a class the sink is handed: one flat "
 "object per line, newline-delimited, which is what every collector already parses. The request id comes from the "
 "MDC &mdash; a ThreadLocal map that is snapshot into the event at creation, not referenced, because with an async "
 "sink the thread that writes the line is not the thread that made it. The failure test proves exactly that: it logs "
 "three hundred lines with rid=req-A, changes the thread's context, then drains, and every line still says req-A. "
 "The extension adds MdcScope, an AutoCloseable so try-with-resources puts the context back on every path out; "
 "without it a pooled thread stamps the last request's id on the next tenant's lines.",
 sect(src, "final class Mdc {", "/**\n * One thing that happened, frozen.")
 + "\n" + X("context that cannot leak", "ship the logs")),
("I cannot debug from \"payment failed\". Put the stack trace on the line — and tell me what that costs.", "functional", 5,
 "The formatter renders the throwable with printStackTrace into a StringWriter, causes and all, and appends it to the "
 "same string it was already building. That single decision is what keeps the invariant intact: the sink still "
 "receives ONE string and still writes it with one write() inside one lock, so thirty physical lines land together "
 "and a second thread throwing at the same instant cannot put a frame in the middle of yours. The unit is a record, "
 "not a line. The cost is real and worth saying out loud: walking a stack is microseconds, not the two hundred and "
 "fifty nanoseconds a plain line costs, which is precisely why formatting sits outside the lock &mdash; if it were "
 "inside, one exception would hold the file against every other thread. The JSON layout does the same thing "
 "differently: the trace becomes an escaped \"stack\" field so the record is still one physical line, which is what a "
 "collector wants. The renderer is a static method on the interface rather than a second method on it, so a formatter "
 "is still a lambda. Test 9 runs eight threads throwing a hundred exceptions each and checks all eight hundred blocks "
 "came back unspliced.",
 sect(src, "    static String stackOf(Throwable t) {", "}\n\n/**\n * A human-readable record")
 + "\n" + sect(src, "    public String format(LogEvent e) {\n        StringBuilder sb = new StringBuilder(96);", "/** Level names padded")
 + "\n" + T("        // 9. a stack trace is many physical lines", "        // 10. the two rule changes")),
("A retry loop logged four hundred thousand identical WARNs and paged us. Cap it, now.", "twist", 8,
 "This is neither a level question nor a sink question &mdash; a retry warning is valid WARN &mdash; so it goes on "
 "the filter seam that already exists. RateLimitFilter keys on logger plus message, keeps a window of how many of "
 "that exact line went through, and denies past the cap; a thousand distinct lines are unaffected and one repeated "
 "line is capped. The counter is a compare-and-set over an immutable window record rather than a lock, because this "
 "sits on the hot path of every call, and the map of keys has a ceiling for the same reason the queue does. ERROR "
 "and above return NEUTRAL: you do not silence the thing that wakes you. SamplingFilter is the same shape for "
 "\"keep one DEBUG in a hundred\". Logger, every appender and every formatter stay shut, which is the O in SOLID "
 "being proved rather than asserted.",
 X("log less", "context that cannot leak")),
("Mask card numbers and e-mail addresses before anything hits disk.", "twist", 5,
 "A MaskingFormatter that implements LogFormatter and wraps another one: the inner layout builds the line and the "
 "wrapper redacts it. Because it is a formatter it runs outside every sink's lock, once, and every sink downstream "
 "of it inherits the redaction &mdash; the same Decorator move as AsyncAppender, one level down. The card pattern is "
 "backed by a Luhn check so a long request id or a timestamp is not redacted by accident, and an address keeps its "
 "domain. The honest caveat to say out loud: redacting a finished line is a backstop, not a policy &mdash; the real "
 "fix is not putting a card number in a log call, and a structured layout that knows which field is sensitive beats "
 "a regular expression over a sentence.",
 X("mask before anything hits disk", "log less")),
("The level configuration must survive a restart, and change without one.", "twist", 5,
 "The levels go behind a two-method repository, LevelStore, that loads and saves a map from logger name to level "
 "name; in memory today, a file or a table tomorrow, with the same two methods. A Configurator reads it and calls "
 "the same setLevel every test calls by hand, so it is a client of the framework rather than a new concept inside "
 "it, and because level is a volatile field a reload takes effect on the very next call. Snapshotting the other way "
 "writes back only the nodes that have an opinion of their own, which is what keeps the file small. Say what does "
 "NOT need a repository: the events themselves, because the log file already is the persistence. The interesting one "
 "is the shipping sink, which clears its buffer only after the send returned &mdash; a failed send leaves the lines "
 "exactly where they were and the next flush retries them &mdash; and stamps each batch with an id so the far side "
 "applies a repeat once. Its retry buffer has a ceiling too: a collector that never comes back sheds down to the cap "
 "and counts every line it gave up on, which the test checks with twenty lines and a transport that always throws.",
 X("configuration that outlives the process", "why System.out is slow")
 + "\n" + X("ship the logs", "configuration that outlives the process")),
("Where does time come from, and how do you test what a line was stamped with?", "design", 3,
 "The context has a Clock it was handed and every event is stamped from it; nothing else in the framework reads the "
 "wall clock. A test sets an instant, logs, moves the instant and logs again, and can then assert the exact "
 "timestamps. The same seam is what makes the time-rolling sink testable: it asks the injected clock which day it "
 "is, so a test rolls three days in a microsecond instead of waiting for midnight. It is also why the rate limiter's "
 "window can be tested: move the clock past the window and the next identical line goes through.",
 "/** Where time comes from. Injected, so a test can stamp an event with any instant it likes. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the context: handed in, defaulted, never read from the wall clock inside a method\n"
 "private volatile Clock clock = System::currentTimeMillis;\n"
 "void setClock(Clock c) { clock = c; }\n\n"
 "// in a test or a demo: pick the instant, then move it\n"
 "long[] now = { 1_789_205_400_000L };\n"
 "ctx.setClock(() -> now[0]);\n"
 "day.info(\"day 0\");\n"
 "now[0] += 86_400_000L;                                  // a day later: the time-rolling sink starts a new file\n"
 "day.info(\"day 1\");\n"),
("Which pattern is where, which SOLID letter is where, and why is LogLevel an enum rather than a class per level?", "design", 8,
 "The tables in moves 10 and 11 are the list; what an interviewer is actually testing is whether you can defend two "
 "of them and refuse the rest. Defend Decorator: AsyncAppender holds any sink and takes it off the caller's thread, "
 "MaskingFormatter holds any layout and redacts what it produced, and neither of the things being wrapped was edited "
 "&mdash; that is what made \"never let a slow disk stall checkout\" one wiring line. Defend Factory, which most "
 "problems do not earn: getLogger must return the same object for a name forever, or a level change at two in the "
 "morning reaches one static field and not the other, so identity is the requirement rather than tidiness. Refuse "
 "Singleton (the context is handed to its callers, which is why a test builds a fresh one) and refuse Builder for "
 "now (four constructor arguments, all four required; it earns its place the day a config file has twenty knobs). "
 "And LogLevel is an enum because the only operation on a level is comparing its severity to another: a class per "
 "level would be six classes and a virtual call on the hottest line in the framework, with no way to write TRACE "
 "&lt; DEBUG as one integer compare.",
 "// Strategy: a rule behind an interface, handed in, never built by the Logger\n"
 "interface LogFormatter { String format(LogEvent e); }\n"
 "ctx.configure(LogLevel.INFO, List.of(console), List.of(new DenyMessageFilter(\"/healthz\")));\n\n"
 "// Decorator: any sink goes off-thread without being edited; any layout gets masked the same way\n"
 "new AsyncAppender(\"async\", fileSink, 8192, OverflowPolicy.BLOCK, LogLevel.ERROR);\n"
 "new MaskingFormatter(new TextFormatter());\n\n"
 "// Template Method: the skeleton is final, the hole is write(), and the lock is already held inside it\n"
 "public final void append(LogEvent e) { /* threshold, format, lock, write, unlock, never throw */ }\n"
 "protected abstract void write(LogEvent e, String line) throws Exception;\n\n"
 "// Observer + Chain of Responsibility: the sinks are the listeners, the filters are the voters\n"
 "logger.addAppender(a);   logger.addFilter(e -> e.message().contains(\"/healthz\") ? DENY : NEUTRAL);\n\n"
 "// Factory: EARNED here, because identity is the requirement, not tidiness\n"
 "Logger l = registry.computeIfAbsent(name, n -> new Logger(n, parent, this));\n\n"
 "// Enum, not a class per level: the only operation is one integer compare on the hottest line in the framework\n"
 "enum LogLevel { TRACE(10), DEBUG(20), INFO(30), WARN(40), ERROR(50), FATAL(60), OFF(Integer.MAX_VALUE); }\n"
 "boolean atLeast(LogLevel bar) { return severity >= bar.severity; }\n"),
]

build(dict(
    slug="logger", title="Logger",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 58 failure checks and a 50-thread race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=DERIVATION_LEAD,
    moves=[(t, MV[k], txt) for (t, txt, k) in MOVES],
    uml_svg=UMLSVG, how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT_CARD,
    followups=FU,
))
