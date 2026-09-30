# Job Scheduler LLD workbench: problem -> twelve moves (4-6 with a prerequisites half) -> the class diagram -> the whole code -> follow-ups.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"job-scheduler/Main.java").read_text()
ext   = (H/"job-scheduler/Extensions.java").read_text()
tests = (H/"job-scheduler/FailureTests.java").read_text()

def cut(s, a, b=None):
    """slice a source from the line holding `a` to just before the line holding `b`; a bare '/**' line just above
    either anchor goes with the Javadoc it opens"""
    def line_start(pos):
        k = s.rfind("\n", 0, pos) + 1
        prev = s.rfind("\n", 0, max(k - 1, 0)) + 1
        return prev if k > 0 and s[prev:k].strip() == "/**" else k
    i = line_start(s.index(a))
    j = len(s) if b is None else line_start(s.index(b, i))
    return s[i:j].rstrip() + "\n"
def X(name):
    """one '// ---- ext:' block of Extensions.java, up to the next block (or the ExtDemo)"""
    i = ext.index("// ---- ext: " + name)
    nxt = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext) if m.start() > i] + [ext.index("/** Runs every extension")]
    return ext[i:min(nxt)].rstrip() + "\n"
def T(a, b):
    """one numbered block of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
PROMPT = ('"Build a job scheduler. A caller submits a job to run after a delay, at a given time, or again and again '
          '(every ten seconds, or ten seconds after the last run ended), and a job may have to wait for other jobs to '
          'finish first. A fixed pool of worker threads runs the jobs, and I need cancel and shutdown. I want working, '
          'thread-safe code, not a diagram. Go."')

pf = _D
rows = [("schedule", 30, [("schedule(spec), any thread", "a delay, a time, or a rhythm"),
                          ("check first, then store", "duplicate id, unknown prereq, a loop"),
                          ("BLOCKED, or into the time heap", "the earliest due job on top"),
                          ("new earliest? signal", "the dispatcher re-plans its sleep")]),
        ("dispatch", 155, [("the dispatcher sleeps", "until the earliest job is due"),
                           ("due, and a worker free?", "take the best: priority, then time"),
                           ("mark RUNNING, under the lock", "from this line on, cancel() loses"),
                           ("a worker runs it", "outside the lock")]),
        ("finish", 280, [("the run ends: ok, or it threw", "even an Error is one failed try"),
                         ("retry, next run, or the end", "backoff; fixed rate or fixed delay"),
                         ("settle the jobs waiting on it", "DONE counts down; failure skips"),
                         ("signal, then tell listeners", "history, metrics: after the unlock")])]
for lab, y, boxes in rows:
    pf += _tx(80, y + 31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 150 + k*270
        pf += _bx(x, y, 250, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+250, y+27, x+270), True)
pf += _ar("M545 84 V96", dash=True) + _bx(400, 96, 290, 36, "a loop or a bad prerequisite: refused", "", dash=True)
pf += _ar("M545 209 V221", dash=True) + _bx(400, 221, 290, 36, "cancelled while waiting: skipped", "", dash=True)
pf += _tx(80, 372, "query", "var(--acc)", 13) + _tx(150, 372, "at any moment, in O(1): status(id), how many jobs in each state; cancel(id) before the start means it never starts", "var(--text)", 12, "start")
pf += _tx(80, 402, "stop", "var(--acc)", 13) + _tx(150, 402, "shutdown() lets accepted one-shot jobs finish; shutdownNow() cancels what has not started and interrupts what runs", "var(--text)", 12, "start")
pf += _tx(615, 440, "many threads schedule and cancel while N workers run jobs: no job is lost or started early, none runs twice at once, none starts after a cancel that said yes", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 456, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("09:00:03  alert, due in 1 s", ["the dispatcher sleeps until 09:00:10", "alert is earlier: the new head", "signal: it wakes, sleeps 1 s", "alert runs 09:00:04; ping at :10"], True),
      ("09:01:00  charge throws", ["attempt 1: gateway timeout", "back in the heap ~1 s later (jitter)", "attempt 2 throws: ~2 s later", "attempt 3 works: DONE; receipt runs"], False),
      ("09:02:00  two builds end at once", ["two workers finish in the same ms", "deploy waits for 2 -> 1 -> 0", "the lock takes them one by one", "exactly one of them queues deploy"], False),
      ("09:05:00  cancel races dispatch", ["backup is due at 09:05:00.000", "cancel arrives in the same ms", "cancel gets the lock first: true", "the dispatcher skips it: no run"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 30 + k*300
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+140) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+140)
    pe += _card(x, 60, 280, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Schedule a job to run once, after a delay or at a clock time, and get back its id.</li>
<li>Recurring jobs: at a fixed rate (counted from each planned start) or with a fixed delay (counted from the end of each run).</li>
<li>Run due jobs on a fixed pool of N worker threads: never on the dispatcher thread, never inside the lock.</li>
<li>Prerequisites: a job may wait for other jobs and runs only after all of them succeeded; a failed or cancelled one skips everything behind it; a loop is refused at submit, with its path.</li>
<li>Retries with exponential backoff and jitter (a random part of each wait, so jobs that failed together do not retry together), up to a limit, then FAILED.</li>
<li>cancel(id): a job that has not started never will. status(id) and the count per state at any moment.</li>
<li>When jobs are due and the workers are busy, priority decides who goes first, and that rule can change.</li>
<li>shutdown() lets accepted one-shot jobs finish; shutdownNow() cancels what has not started and interrupts what runs (asks its thread to stop).</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many threads submit and cancel at once: no job is lost, and none starts early, runs twice at the same time, or starts after a cancel that returned true.</li>
<li>The dispatcher sleeps exactly until the next job is due and wakes at once for an earlier one: no polling, no lost wakeups (a signal sent before anyone waits, and so never heard).</li>
<li>schedule and dispatch are O(log n) (a heap); cancel and status are O(1) (a map).</li>
<li>Back-pressure (slowing or refusing callers when work arrives faster than it is done): a worker gets a job only when it is free, and new jobs are refused past a limit, so a flood fills neither memory nor a queue.</li>
<li>The rules that change (when next, how to retry, which due job first) are swapped without opening the scheduler.</li>
<li>A job that throws, even an Error, never kills a worker or the dispatcher and never loses a worker slot.</li>
<li>Time comes from an injected clock, so every timing rule is tested without sleeping.</li>
<li>In memory, one process (say it; a follow-up adds a jobs table and many machines).</li></ul></div></div>
'''

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>A job is a piece of code with a time attached: send the '
 'nightly report at 02:00, retry this payment in five seconds, ping this server every ten seconds. Callers on many '
 'threads hand jobs to the scheduler and go back to their own work. The scheduler must start each job when its time '
 'comes, on one of a fixed number of worker threads, and never on the thread that watches the clock (the dispatcher). Some jobs wait for '
 'others: deploy runs only after both builds have succeeded, and if a build fails, deploy must not run at all. Jobs '
 'fail and are retried later, jobs get cancelled, and the whole thing gets shut down. The one thing that must always be '
 'true (the invariant): no accepted job is lost, and none starts before its time or its prerequisites, runs twice at '
 'the same moment, or starts after a cancel that succeeded; and no more than N jobs run at once.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with a '
 '<code>main</code> that schedules a few jobs and shows them starting at the right times. The interviewer is watching '
 'for, in this order: the questions you ask before typing; which class owns the queue of jobs (a heap: a tree that always '
 'keeps the earliest job on top) and the lock; the '
 'dispatcher\'s wait loop, and what wakes it when an earlier job arrives (this is where most candidates lose marks); '
 'what happens when cancel and the dispatcher reach the same job at the same instant; where the rules that will change '
 'live (when a job runs next, how it is retried, which due job goes first), so a new rule is a new class; and what '
 'happens when a job throws. Then the twists: prerequisites and loops, cron lines with time zones, jobs that need a '
 'machine with a GPU, and several scheduler machines sharing one jobs table. The JDK already has '
 '<code>ScheduledThreadPoolExecutor</code>; the interviewer asks you to build it anyway, because the wait-and-signal '
 'protocol inside it is the question.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>How many worker threads, and may jobs run at the same time?</td><td>A fixed pool of N; yes</td><td>One dispatcher, N workers, one lock (moves 1, 4, 7)</td></tr>'
 '<tr><td>One-shot jobs only, or recurring? Fixed rate or fixed delay?</td><td>Both kinds and both rhythms</td><td>The Trigger rule (move 3)</td></tr>'
 '<tr><td>What if a run takes longer than its period?</td><td>Never two runs at once; missed runs merge into one late run</td><td>Back in the heap only after the run ends; the Misfire rule (move 6)</td></tr>'
 '<tr><td>What if a job throws? Retry?</td><td>Exponential backoff (each wait twice the last), at most 3 attempts, then FAILED</td><td>The RetryPolicy rule and the order after a run (moves 3, 6)</td></tr>'
 '<tr><td>Can a job wait for other jobs? What if one fails, or they form a loop?</td><td>Yes; skip whatever depends on a failure; refuse a loop at submit</td><td>A count and a list per job, and a cycle check (moves 4, 5, 6)</td></tr>'
 '<tr><td>Cancel before it starts? While it runs?</td><td>Before: it never runs. During: this run finishes, nothing follows</td><td>Cancel and dispatch both decide under the lock (moves 4, 6)</td></tr>'
 '<tr><td>When jobs are due and every worker is busy, who goes first?</td><td>Higher priority, then earlier due, then first come</td><td>A second heap, ordered by a rule handed in (moves 3, 5)</td></tr>'
 '<tr><td>Finish the queued work on shutdown, or stop now? One process, in memory?</td><td>Both calls exist; one process</td><td>shutdown() and shutdownNow(); a jobs table later (moves 6, 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One morning, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> one scheduler, in memory, one process; N worker threads plus one '
 'dispatcher that never runs a job; times in epoch milliseconds (counted from 1 January 1970, UTC) from an injected '
 'clock; fixed rate counts from the '
 'planned start and fixed delay from the end of the run; a job goes back into the heap only after its run ends; a '
 'failure is retried with backoff, then FAILED; a failed or cancelled prerequisite skips whatever waits for it. Named '
 'as out of scope: cron lines and time zones, per-job time limits, jobs that need a GPU machine, several scheduler '
 'machines on one jobs table; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a CALLER submits a JOB for a DELAY or a RHYTHM; it may WAIT FOR other jobs; a DISPATCHER wakes; a WORKER runs it; a failure is RETRIED", "var(--text)", 12.5)
for k, (t, s, acc) in enumerate([("ScheduledJob", "task, times, state, tries", 1), ("Scheduler", "heaps, jobs by id, the lock", 1),
                                 ("JobSpec", "what the caller asks for", 1), ("Trigger, RetryPolicy", "a rule: an interface", 0),
                                 ("Dispatcher", "a thread: a loop inside", 0), ("Worker", "a thread: take, run, report", 0)]):
    x = 20 + k*200
    m1 += _bx(x, 110, 185, 46, t, s, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + 92))
m1 += _tx(615, 190, "solid = state of its own, so a class.   dashed = a rule (move 3), or a thread: a loop inside the class that owns what it touches", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("put a job in time order", "Scheduler  (owns the heaps + the lock)", "schedule(spec)"),
                                       ("take every job that is due", "Scheduler  (the same heaps)", "pollDue(now)"),
                                       ("work out when it runs next", "Trigger  (touches no state: pure)", "trigger.next(planned, ended)"),
                                       ("run the job's own code", "a worker thread, outside the lock", "runJob(job) -&gt; task.run()")]):
    y = 20 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "who does it: no state of its own" if k == 3 else "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 262, "a verb that touches the heaps goes to their owner; a verb that touches nothing becomes a pure rule, which is what makes it swappable", "var(--muted)", 11)
MV[2] = _mv(1230, 278, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 110, 220, 90, "Scheduler + JobSpec", "handed in, never built", acc=True)
for k, (t, s, impl) in enumerate([("Trigger", "when it runs next", "FixedRate / FixedDelay / Cron"),
                                  ("RetryPolicy", "how long before a retry", "NONE / ExponentialBackoff"),
                                  ("Comparator&lt;ScheduledJob&gt;", "which due job goes first", "HIGHEST_PRIORITY_FIRST / BY_DUE / Aging"),
                                  ("RunListener", "who hears about each run", "RunHistory / metrics / a pager"),
                                  ("Clock", "where time comes from", "Clock.system() / ManualClock")]):
    y = 18 + k*54
    m3 += _ar("M250 155 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 300, 44, t, s, dash=True)
    m3 += _bx(760, y, 440, 44, impl, "the classes that can be handed in") + _ar("M760 %s H700" % (y+22))
m3 += _tx(615, 305, "dashed green = handed in: per job on its JobSpec, per scheduler through configure() and the constructor. The scheduler builds none of them", "var(--muted)", 11)
m3 += _tx(615, 325, "and one rule can WRAP another: new SkipHolidays(Cron.parse(\"30 9 * * 1-5\", IST), IST, holidays). That wrapping is Decorator, born right here.", "var(--acc)", 11)
MV[3] = _mv(1230, 340, m3)

# move 4: the gaps -> one owner, one lock, decide-and-wait as one step
m4 = _D + _bx(30, 30, 200, 44, "caller: cancel(backup)", "reads: SCHEDULED") + _bx(30, 120, 200, 44, "the dispatcher", "reads: SCHEDULED, due")
m4 += _bx(320, 75, 160, 44, "job backup", "SCHEDULED", acc=True)
m4 += _ar("M230 52 H320 V75") + _ar("M230 142 H320 V119") + _tx(275, 42, "read", "var(--muted)", 10.5) + _tx(275, 170, "read", "var(--muted)", 10.5)
m4 += '<rect x="510" y="18" width="340" height="170" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(680, 40, "the two gaps", RED, 12)
for k, l in enumerate(["1 both saw SCHEDULED: cancel says true,", "  and the dispatcher runs it anyway",
                       "2 it plans to sleep until 09:00:10; alert,", "  due 09:00:04, signals before it waits"]):
    m4 += _tx(525 + (14 if l.startswith("  ") else 0), 64 + k*20, l.strip(), RED, 11, "start")
m4 += _tx(680, 160, "fix: check + act, and decide + wait, as ONE step", "var(--text)", 11)
m4 += _bx(880, 40, 320, 100, "Scheduler.lock + one Condition", "heaps, map, states, counts: one lock", acc=True)
m4 += _tx(1040, 165, "await() lets go of the lock only once it is waiting", "var(--muted)", 10.5)
m4 += _tx(1040, 185, "listeners are called after the unlock, never inside", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

m4b = _D + _bx(30, 30, 200, 44, "build-a ends", "on worker 1") + _bx(30, 120, 200, 44, "build-b ends", "on worker 2, same ms")
m4b += _bx(320, 75, 160, 44, "deploy", "waitingFor = 2", acc=True)
m4b += _ar("M230 52 H320 V75") + _ar("M230 142 H320 V119") + _tx(275, 42, "count - 1", "var(--muted)", 10.5) + _tx(275, 170, "count - 1", "var(--muted)", 10.5)
m4b += '<rect x="510" y="18" width="340" height="170" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4b += _tx(680, 40, "the gap", RED, 12)
for k, l in enumerate(["both read 2 and both write 1:", "  deploy waits for ever", "or both see 0:", "  deploy is queued twice"]):
    m4b += _tx(525 + (14 if l.startswith("  ") else 0), 64 + k*20, l.strip(), RED, 11, "start")
m4b += _tx(680, 160, "fix: count down and test for 0 under the lock", "var(--text)", 11)
m4b += _bx(880, 40, 320, 100, "endLocked(), under the lock", "the two finishes go one after the other", acc=True)
m4b += _tx(1040, 165, "exactly one of them sees 0 and queues deploy", "var(--muted)", 10.5)
MV["4b"] = _mv(1230, 200, m4b)

# move 5: each collection -> its question -> its shape
m5 = _D
for k, (q, shape, cost) in enumerate([("which job is due next?", "PriorityQueue by dueAt: look at the head", "O(1) peek, O(log n) add"),
                                      ("of the due ones, which goes first?", "a second PriorityQueue, its order handed in", "O(log n)"),
                                      ("this job, by id? (cancel, status)", "HashMap&lt;id, ScheduledJob&gt;", "O(1)"),
                                      ("take a cancelled job out of a heap?", "no: mark it CANCELLED, drop it at the top", "O(1), not O(n)"),
                                      ("how many waiting, running, failed?", "EnumMap&lt;JobState, Integer&gt;, kept by move()", "O(1)"),
                                      ("give a due job to a worker?", "LinkedBlockingQueue: the dispatcher puts, workers take", "O(1)")]):
    y = 16 + k*46
    m5 += _bx(30, y, 350, 38, q, "the question") + _ar("M380 %s H430" % (y+19), True)
    m5 += _bx(430, y, 520, 38, shape, "the shape", acc=True) + _ar("M950 %s H1000" % (y+19), True) + _bx(1000, y, 200, 38, cost, "")
m5 += _tx(615, 306, "not one of these is a scan, and every scan would have been inside the lock", "var(--muted)", 11)
MV[5] = _mv(1230, 320, m5)

m5b = _D
for (x, y, t, s, acc) in [(30, 26, "build-a", "DONE", False), (30, 116, "build-b", "RUNNING", False),
                          (290, 71, "deploy", "waitingFor 1", True), (540, 71, "smoke", "waitingFor 1", False),
                          (290, 150, "lint", "waitingFor 0: due", False)]:
    m5b += _bx(x, y, 180, 44, t, s, acc=acc)
m5b += _ar("M210 48 H250 V82 H290") + _ar("M210 138 H250 V104 H290") + _ar("M470 93 H540")
m5b += _tx(130, 190, "arrows: dependents lists", "var(--muted)", 10.5)
for k, (q, a, c) in enumerate([("may deploy start yet?", "int waitingFor: 0 means yes", "O(1)"),
                               ("who waits for build-b?", "List dependents on build-b", "O(k), once, at its end"),
                               ("is there a loop in this batch?", "Kahn's count at submit, then a walk", "O(jobs + links), once")]):
    y = 26 + k*58
    m5b += _bx(760, y, 440, 46, q + "  " + c, a, acc=(k == 0))
MV["5b"] = _mv(1230, 210, m5b)

# move 6: the state machine and the ORDER after every run
m6 = _D
for (x, t, s, acc) in [(30, "BLOCKED", "waits for prerequisites", True), (215, "SCHEDULED", "waits for time, a worker", True), (400, "RUNNING", "handed to a worker", True)]:
    m6 += _bx(x, 40, 160, 44, t, s, acc=acc)
m6 += _ar("M190 62 H215", True) + _ar("M375 62 H400", True)
m6 += _ar("M480 40 V20 H295 V40", True) + _tx(388, 15, "retry, or the next run", "var(--acc)", 10.5)
for (x, t, s) in [(30, "SKIPPED", "a prerequisite failed"), (215, "CANCELLED", "cancel, or shutdown"), (400, "DONE | FAILED", "ok, or gave up")]:
    m6 += _bx(x, 150, 160, 44, t, s)
m6 += _ar("M110 84 V150") + _ar("M295 84 V150") + _ar("M480 84 V150") + _ar("M430 84 V110 H330 V150", dash=True)
m6 += _tx(380, 104, "cancel mid-run", "var(--muted)", 10)
m6 += '<rect x="600" y="16" width="610" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(905, 40, "the order after every run, inside finishLocked, and why", "var(--text)", 12)
for k, l in enumerate(["1 free the worker slot: running - 1",
                       "2 failed, attempts left? back in the heap at end + backoff, same slot",
                       "3 recurring? next planned time; if already past, Misfire decides",
                       "4 otherwise DONE, or FAILED",
                       "5 DONE counts the waiting jobs down; any other end skips them",
                       "6 signal the dispatcher; tell the listeners after the unlock"]):
    m6 += _tx(615, 64 + k*22, l, "var(--text)", 11, "start")
m6 += _tx(905, 198, "a job is back in a heap only AFTER its run ended: two runs never overlap", "var(--acc)", 11)
m6 += _tx(615, 232, "the dispatcher marks a job RUNNING under the lock before any worker sees it: from that line on, cancel() returns false, and the job runs", "var(--muted)", 11)
MV[6] = _mv(1230, 248, m6)

m6b = _D + _card(30, 20, 250, 128, "the batch", ["x waits for z", "y waits for x", "z waits for y", "w waits for nothing"])
m6b += _ar("M280 84 H330", True)
m6b += _card(330, 20, 520, 148, "scheduleAll: every check BEFORE anything is created",
             ["1 duplicate ids?  2 every prerequisite known, none recurring?",
              "3 a loop? Kahn: keep removing jobs that wait for nothing",
              "  in the batch. Left over: x, y, z. Each still waits for one",
              "  of the others, so walking 'waits for' must repeat:",
              "  x -> z -> y -> x"], acc=True)
m6b += _ar("M850 84 H900", True)
m6b += '<rect x="900" y="20" width="300" height="148" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
for k, l in enumerate(["refused, with the path:", "cycle, each waits for the next:", "x -> z -> y -> x", "and w is not kept either:", "all or nothing"]):
    m6b += _tx(1050, 46 + k*24, l, RED if k < 3 else "var(--text)", 11)
MV["6b"] = _mv(1230, 182, m6b)

# move 7: what is inside the lock, and eight callers at the same instant
m7 = _D + _card(30, 20, 540, 150, "inside the lock: about half a microsecond a visit",
                ["schedule: a map put and one heap insert, ~0.5 us",
                 "dispatch: heap polls, a state write, a queue put",
                 "finish: a few field writes, maybe one heap insert",
                 "measured: ~1.5 us for all three, 250,000 jobs in heaps",
                 "and the rules it calls: trigger, retry, priority (pure)"], acc=True)
m7 += _ar("M570 95 H640", True) + _tx(605, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(640, 20, 560, 150, "outside the lock: milliseconds to minutes",
            ["the job's own code", "the listeners: history, metrics, a pager",
             "the dispatcher's sleep: await() has let go of the lock", "a caller building its JobSpec"])
m7 += _tx(615, 200, "eight callers call schedule() at the same instant", "var(--text)", 12)
for k in range(8):
    x = 30 + k*148
    m7 += _bx(x, 214, 136, 40, "caller %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%.1f" % (k*0.5)), acc=(k == 7))
m7 += _tx(615, 282, "the eighth waits about 3.5 microseconds and goes back to its own work; the job itself runs later, for milliseconds, on a worker", "var(--muted)", 11)
m7 += _tx(615, 300, "one at a time is true, and nobody can tell, as long as no job's code ever runs inside the lock", "var(--muted)", 11)
MV[7] = _mv(1230, 314, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["~1.5 us of lock per job: schedule + dispatch + finish",
                       "a busy service: 50,000 jobs waiting, 2,000 runs a second",
                       "2,000 x 1.5 us = 3 ms of lock a second: 0.3% busy",
                       "8 workers, 4 ms jobs: 2,000 a second fills the WORKERS",
                       "the lock fills near 650,000 jobs/s; workers run out first"]):
    m8 += _tx(35, 66 + k*24, l, RED if k == 4 else "var(--muted)", 11, "start")
m8 += _tx(900, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, s) in enumerate([("1 K shards: K locks, K heaps, K dispatchers", "job to shard hash(id) mod K; priority per shard only"),
                            ("2 a timing wheel instead of a heap", "O(1) add and cancel for millions of timers (Kafka, Netty)"),
                            ("3 many machines, one jobs table", "claim by a conditional UPDATE with a lease; idempotent jobs")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, s, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("an earlier job arrives mid-sleep", "decide and wait in one locked step, signal a new head; test 2: a 50 ms job runs at ~55 ms, not 5 s"),
                                ("cancel and dispatch reach one job", "both decide under the lock; test 4: 2,000 races, each job ran once or was cancelled"),
                                ("a run is longer than its period", "back in the heap only after it ends; test 7: never two at once; the three misfire timings"),
                                ("a job throws, even an Error", "the worker catches Throwable; a broken rule fails only its own job; test 9: the worker runs on"),
                                ("two prerequisites end together", "count down and test for 0 under the lock; test 11: 30 rounds, deploy runs once"),
                                ("a prerequisite fails", "skip everything behind it, the rest still runs; test 12"),
                                ("a batch with a loop", "check it before anything is created; test 13: refused with its path, nothing kept"),
                                ("shut down with work inside", "shutdown() drains one-shots and stops recurring; shutdownNow() interrupts; tests 14, 15")]):
    y = 16 + k*42
    m9 += _bx(30, y, 330, 36, bad, "") + _ar("M360 %s H410" % (y+18), True) + _bx(410, y, 790, 36, fix, "", acc=True)
m9 += _tx(615, 364, "every claim on this page has a failure test: FailureTests.java runs sixteen of them and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 378, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 190), ("the line in the code", 290), ("what it buys", 880)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("Trigger.next(plannedAt, finishedAt); RetryPolicy.delayMs(...); the Comparator", None), ("a new rule is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new SkipHolidays(Cron.parse(\"30 9 * * 1-5\", IST), IST, holidays)", None), ("add to a rule instead of copying it", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(events) after the unlock; RunHistory implements RunListener", None), ("history and alerts never slow a job", None)],
          [("State", "var(--text)"), ("move 6", None), ("JobState.ALLOWED + move(): the one place a state changes", None), ("an illegal move throws", None)],
          [("Command", "var(--text)"), ("move 1", None), ("a Task: work packed as an object, stored, run later, retried", None), ("the scheduler never knows what a job does", None)],
          [("Builder", "var(--text)"), ("move 1", None), ("JobSpec.of(\"backup\", task).in(300_000).retry(r).after(\"snapshot\")", None), ("six optional settings, one readable line", None)],
          [("Producer-consumer", "var(--text)"), ("move 5", None), ("the hand-off queue: the dispatcher puts, N workers take", None), ("the workers never touch the heaps", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("every test builds its own Scheduler; nothing calls getInstance()", "var(--muted)"), ("no global state to reset", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("Triggers.parse(\"cron 30 9 * * 1-5 Asia/Kolkata\") once schedules come as text", "var(--muted)"), ("today triggers arrive as objects", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 335, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 350, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 440), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("ScheduledJob: one job's facts. Trigger: when next. Scheduler: the flow and the lock.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("Cron, SkipHolidays and Aging were added as classes; Scheduler was never opened", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("j.trigger.next(j.plannedAt, finishedAt);  never \"is this the cron one?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Task, Clock, Trigger, RetryPolicy, RunListener: one method; a fake is a lambda", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations handed in", None), ("moves 3, 9", None), ("new Scheduler(4, new ManualClock(0));  spec.retry(new ExponentialBackoff(...))", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, s, fix, sub2, mv) in enumerate([
        ("a new rule", "a cron line, holidays, aging, a time limit", "a new class behind Trigger, RetryPolicy or the comparator", "", "move 3"),
        ("someone new wants to know", "history, metrics, a pager on FAILED", "one more RunListener; the scheduler does not change", "", "move 4"),
        ("a new step in a life", "PAUSED, TIMED_OUT, WAITING_FOR_MACHINE", "a new state and one row in ALLOWED", "", "move 6"),
        ("a new invariant across jobs", "at most 2 reports at once; a GPU job", "checked inside the same lock at dispatch, or a bulkhead", "", "move 4"),
        ("state that must outlive the process", "a restart; three scheduler machines", "a jobs table behind a repository; the claim becomes",
         "UPDATE jobs SET owner=?, lease_until=? WHERE id=? AND lease_until &lt; now: 1 row = yours", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, s) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "for all five the heaps, the lock and the dispatcher's loop do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

def half(pic, para, title, pic2):
    """picture slot for a move with a second half: its picture, its paragraph, then the second half's heading and picture"""
    return (pic + '<div class="move"><p>' + para + '</p></div>'
            + '<div class="move"><h4 style="margin:12px 0 4px;font-size:14px;color:var(--acc2)">' + title + '</h4></div>' + pic2)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class, and a thread is not a noun.", MV[1],
 "Reading the prompt again: a <b>caller</b> submits a <b>job</b> to run after a <b>delay</b> or on a <b>rhythm</b>; it may "
 "<b>wait for</b> other jobs; a <b>dispatcher</b> wakes when one is due; a <b>worker</b> runs it; a failed run is "
 "<b>retried</b>. A job has a task, a due time, a state and a count of attempts, so it is a class: ScheduledJob. What the "
 "caller asks for (an id, a task, a delay, a rhythm, a retry rule, a priority, the jobs to wait for) is a class too, "
 "JobSpec, filled in with chained calls. The scheduler holds every job, the queue ordered by time and the lock: a class, "
 "and the only one with a lock. \"When does it run next\" and \"how long before a retry\" are rules, not things, so they "
 "become interfaces in move 3. Notice what did not become a class: the dispatcher and the workers. A thread has no state "
 "worth modelling of its own; it is a loop that runs inside the class that owns the state it touches. The scheduler owns "
 "the heap, so the dispatcher's loop and the workers' loop are private methods of Scheduler, started by "
 "<code>start()</code>."),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.", MV[2],
 "\"Put a job in time order\" changes the heap, so it belongs to whoever owns the heap: <code>schedule(spec)</code> on "
 "Scheduler. \"Take every job that is due\" reads and changes the same heap: <code>pollDue(now)</code>, also on "
 "Scheduler. \"Cancel\" changes a job's state, which only the scheduler changes, under its lock: "
 "<code>cancel(id)</code>. \"Work out when it runs next\" touches no state at all. Given the planned start and the end "
 "of the last run it returns a time, so it is a pure function (it reads its inputs and changes nothing) on the job's "
 "Trigger, and that is exactly why it can be swapped. \"Run the job's code\" is the one verb that must never happen "
 "inside the scheduler's lock, because it takes milliseconds to minutes. The worker calls <code>runJob(job)</code>, "
 "which runs the task with no lock held and only then takes the lock to record what happened."),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.", MV[3],
 "When a job runs next will change: every ten seconds today, ten seconds after the last run ended tomorrow, 09:30 on "
 "weekdays in Mumbai the day after. How long to wait before a retry will change: never, then exponential backoff, then "
 "\"not for this kind of error\". Which due job goes first when the workers are busy will change: priority today, "
 "priority with aging (a waiting job's priority slowly rising) when someone complains about starvation (a job that "
 "waits for ever because others keep going first). Who wants to hear about finished runs will grow: a "
 "history, a metrics counter, a pager for FAILED. And the clock must be one a test can move. Each becomes a one-method "
 "interface the scheduler is <i>given</i> and never builds: a job's Trigger and RetryPolicy come in on its JobSpec, the "
 "priority rule through <code>configure()</code>, listeners through <code>addListener()</code>, the clock through the "
 "constructor. The rules run inside the lock, so they must be pure and fast: a cron calculation, never a database call. "
 "This is where the patterns come from, not the other way round: a swappable rule behind an interface is "
 "<b>Strategy</b>; a rule that wraps another, like a holiday calendar around a cron line, is <b>Decorator</b>; a "
 "scheduler that tells whoever subscribed that a run ended, without knowing who they are, is <b>Observer</b>. Do them; "
 "do not announce them. What happens to missed runs is a rule too, but it has exactly three answers, so it is an enum, "
 "Misfire, not an interface."),
("Move 4: state that many threads change at the same time gets one owner and one lock, and deciding to sleep is part of the same step.",
 half(MV[4],
 "Callers on many threads schedule and cancel while the dispatcher takes due jobs and the workers report results. Two "
 "gaps open the moment any of that is not one step. The first is cancel against dispatch. The dispatcher reads "
 "\"backup is SCHEDULED and due\", a caller reads the same, marks it cancelled and returns true, and the dispatcher hands "
 "backup to a worker anyway: a cancel that said yes, and a job that ran. The second is the lost wakeup (a signal sent "
 "while nobody is waiting yet, and so heard by nobody). The dispatcher looks at the heap, sees ping due at 09:00:10 and "
 "decides to sleep ten seconds. Before it actually starts waiting, a caller adds alert for 09:00:04 and signals. Nobody "
 "was waiting, so the signal is gone, and alert runs six seconds late. So every piece of shared state (the two heaps, "
 "the map of jobs, each job's state, the counts) lives in Scheduler under one ReentrantLock. The dispatcher decides how "
 "long to sleep and starts sleeping in the same locked step, on a Condition (a waiting room tied to the lock: "
 "<code>await</code> sleeps in it, <code>signal</code> wakes one sleeper). <code>awaitNanos</code> lets go of the "
 "lock only once the thread is waiting, so a caller's signal can only arrive while the dispatcher is listening. Anyone "
 "who only listens (history, metrics) is called after the lock is released.",
 "Prerequisites, part 1 of 3: two prerequisites finishing at the same instant", MV["4b"]),
 "The same gap has a third form once jobs wait for jobs. Deploy waits for build-a and build-b, so it keeps a count, "
 "waitingFor, which starts at 2. The two builds end in the same millisecond on two workers, and each does count = "
 "count - 1. Without the lock, both can read 2 and both write 1, and deploy waits for ever; or both see the count reach "
 "0, and deploy is queued twice. With the decrement and the \"is it zero now?\" check inside the scheduler's lock, the "
 "two finishes happen one after the other, and exactly one of them sees 0 and queues deploy. Test 11 runs this thirty "
 "times, with eight prerequisites released by a barrier (a gate that lets all eight finish at the same instant)."),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1) or O(log n).",
 half(MV[5],
 "\"Which job is due next?\" is a heap (a tree kept so that the smallest item is always on top) ordered by due time: "
 "peek at the head in O(1), add or remove in O(log n), 17 steps for 100,000 jobs. \"Of the due ones, which goes "
 "first?\" is a second question with a different answer, so it gets a second heap, ordered by the rule handed in "
 "(priority by default). A job moves from the first heap to the second when its time comes. \"This job, by id\" is a "
 "map, for cancel and status. \"Take a cancelled job out of the heap\" is the trap: <code>PriorityQueue.remove(job)</code> "
 "is a scan, O(n), inside the lock. So a cancelled job is only marked CANCELLED and stays where it is, and the dispatcher "
 "drops it when it reaches the top (lazy removal). \"How many are waiting, running, failed\" is seven numbers kept up to "
 "date by the one method that changes a state. The hand-off to the workers is a queue the dispatcher puts into and the "
 "workers take from, and the dispatcher hands out only as many jobs as there are free workers: the queue never holds "
 "more than N, and the rest wait in the ready heap, where priority still decides who goes next. The map keeps "
 "finished jobs so that status(id) can answer; a long-running scheduler keeps only a "
 "recent window of them.",
 "Prerequisites, part 2 of 3: one number and one list per job", MV["5b"]),
 "Prerequisites add three questions. \"May this job start yet?\" is one number per job, waitingFor, the count of "
 "prerequisites not yet DONE: zero means yes. \"Who is waiting for me?\" is a list on each job, dependents, walked once "
 "when the job ends: a success counts each one down, any other end skips each one and everything behind it. \"Is there "
 "a loop in this batch?\" is asked once, at submit, with Kahn's algorithm (keep removing jobs that wait for nothing still "
 "in the batch; any that are left sit on or behind a loop), then a walk along \"waits for\" links from a leftover job "
 "until one repeats, which prints the loop. Both are plain loops, not recursion, so a chain of 20,000 jobs cannot "
 "overflow the call stack."),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 half(MV[6],
 "A job is BLOCKED while it waits for prerequisites, SCHEDULED while it waits for its time or a free worker, RUNNING once "
 "the dispatcher has handed it to a worker, and then DONE, FAILED, CANCELLED or SKIPPED, which it never leaves. A "
 "RUNNING job can also go back to SCHEDULED: a retry, or a recurring job's next run. The ALLOWED table in JobState is "
 "the whole state machine, and every change goes through one method, <code>move()</code>, which throws on anything "
 "else and keeps the counts right. Writing the states down forces the question the interviewer will ask: what if a "
 "ten-second job runs every five seconds? The answer is an order. After the run, <code>finishLocked</code> decides, "
 "under the lock: a retry at end + backoff (the same planned slot, one more attempt), or the next planned run, or the "
 "end. The job goes back into a heap only after its run has ended, so two runs of one job can never overlap, however "
 "short the period. Fixed rate counts the next run from the planned start and fixed delay from the end of the run. A "
 "planned time that has already passed is a misfire (a run that could not start on time), and the job's Misfire "
 "decides: run every missed one, run one for all of them now, or skip to the next. Only then are the waiting jobs "
 "settled, the dispatcher signalled and, after the unlock, the listeners told.",
 "Prerequisites, part 3 of 3: submitting is all or nothing", MV["6b"]),
 "Submitting has an order too. <code>scheduleAll</code> checks everything before it creates anything: no duplicate ids, "
 "every prerequisite known, none of them recurring (a job cannot wait for something that never finishes), and no loop. "
 "A batch where x waits for z, z for y and y for x is refused with the message \"cycle, each waits for the next: x -> z "
 "-> y -> x\", and w, which was fine, is not kept either: a batch is all or nothing, so a caller who fixes the loop and "
 "submits again never meets half a batch. Only after every check passes are the jobs created BLOCKED, linked to what "
 "they wait for, and those that wait for nothing moved to SCHEDULED. A job whose prerequisite has already failed is "
 "SKIPPED on the spot rather than accepted and left waiting for ever. Cancel follows the same rule as failure: "
 "cancelling backup skips upload, which waited for it (Media.net's \"cancel a task and its dependents\")."),
("Move 7: yes, the lock makes schedule, dispatch and finish happen one at a time. Ask for how long, and what is inside it.", MV[7],
 "The question you will be asked: if every schedule, dispatch and finish takes the same lock, is the scheduler "
 "one-at-a-time? It is, for about half a microsecond a visit. Inside the lock there is a map put, a heap insert or two "
 "heap polls, and a few field writes; measured here, all three visits for one job come to about one and a half "
 "microseconds, with 250,000 jobs in the heaps. Everything slow is outside: the job's own code, the listeners, and the "
 "dispatcher's sleep, because <code>await()</code> lets go of the lock while it waits, so a sleeping dispatcher never "
 "blocks a caller. When eight callers schedule at the same instant, the eighth waits about three and a half "
 "microseconds, then goes back to its own work, while the job runs later, for milliseconds, on a worker. One at a time is "
 "true, and nobody can tell, as long as no job's code ever runs inside the lock. The rules do run inside it (the "
 "trigger, the retry policy, the priority comparator), which is why they must be pure and fast."),
("Move 8: say the arithmetic, then name the ladder.", MV[8],
 "Say the numbers first. About one and a half microseconds of lock per job, all three visits together. A busy service "
 "with 50,000 jobs waiting and 2,000 runs a second holds the lock three milliseconds in every second: 0.3% busy. The "
 "workers run out long before the lock does: at 4 ms a job, eight workers are full at 2,000 jobs a second, while the "
 "lock would only fill near 650,000. So the first answer to \"too slow\" is more workers, or a separate pool per kind "
 "of job, not a cleverer lock. Until then jobs pile up in the heaps, so the door needs back-pressure too: "
 "<code>limitPending(max)</code> refuses new jobs while max are unfinished. Then the ladder, in the order you would "
 "climb it. Rung one: K schedulers, each with its "
 "own lock, heaps and dispatcher, a job going to the shard (the slice of jobs one of them owns) hash(id) mod K; priority then holds only within a shard, and "
 "a batch with prerequisites must go to one shard. Rung two: a timing wheel instead of a heap (an array of buckets, one "
 "per tick of time, like the face of a clock), which makes adding and cancelling O(1) for millions of timers; Kafka and "
 "Netty use one. Rung three: many machines, one jobs table, each job claimed with a conditional UPDATE and a lease (a "
 "claim that expires on its own). For "
 "comparison, the JDK's own ScheduledThreadPoolExecutor is one lock around one heap."),
("Move 9: list what can go wrong, and write the test for each before the interview is over.", MV[9],
 "Each row is a few lines in FailureTests.java, which runs sixteen such tests and prints ALL PASS or exits non-zero. "
 "The two worth writing in front of the interviewer are the first two. The lost wakeup: put the dispatcher to sleep "
 "towards a job five seconds away, add one for fifty milliseconds, and measure; remove the signal and the test waits "
 "the full five seconds and fails. And cancel against dispatch: 2,000 jobs, a thread cancelling them in random order "
 "while the dispatcher starts them, and afterwards every job either ran once or was cancelled, never both and never "
 "neither. The two candidates forget are the last two: a batch with a loop, and a shutdown with work still inside. "
 "Timing rows use a ManualClock and never sleep; race rows use real threads and a latch (a gate that opens for all "
 "of them at once) or a barrier."),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.", MV[10],
 "The table is the answer; each name has one sentence behind it because a move produced it. This system earns two "
 "that most LLD pages do not. Command, because a Task is exactly that: a piece of work packed into an object, so it can "
 "wait in a heap, run later on another thread, and run again after a failure. Builder, because a job really has six "
 "optional settings, and <code>JobSpec.of(\"backup\", task).in(300_000).retry(r)</code> reads better than a constructor "
 "with eight arguments. The last two rows are the absences, worth saying out loud: no Singleton, because every test "
 "builds its own scheduler, and no Factory until schedules arrive as text, which is the <code>Triggers.parse</code> in "
 "Extensions.java. A pattern without a move behind it is decoration."),
("Move 11: run SOLID as a check on the moves, one line each.", MV[11],
 "SOLID is not a list to recite; it is the check that the moves did their job. The honest answer to \"which principles "
 "did you apply?\" is \"move 2 gave me S, move 3 gave me O, L, I and D\" rather than five definitions. The one worth "
 "showing rather than claiming is D: because the clock is handed in, a test can say \"it is now 09:30 on a Monday\" "
 "and a five-day cron schedule runs in a few milliseconds, and because the task is an interface, <code>() -&gt; { throw "
 "new IOException(); }</code> is a failing job in one line."),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.", MV[12],
 "Two of the five need more than the picture gives them. A new invariant across jobs has two answers. At most two report "
 "jobs at a time is a bulkhead (a separate small scheduler per kind of job, so one kind can never take another's "
 "workers), and needs no change at all. A job that needs a GPU is a placement decision made under one lock, like "
 "dispatch, and Extensions.java has both. And state that must outlive the process moves into a jobs table: every "
 "scheduler machine polls it, and taking a job becomes a conditional UPDATE with a lease (a claim that expires), the "
 "database's compare-and-set (change a row only if it still holds what you read, in one step). A machine that dies "
 "mid-job lets its lease expire and another machine runs the job again, "
 "so jobs run at least once, never exactly once, and must be idempotent (safe to run twice). For all five the heaps, "
 "the lock and the dispatcher's loop do not change; that is the test that the derivation was right. Page 05 has the "
 "code for each."),
]

# ============================================================ page 03: the class diagram
uml_reset()
put("caller", 10, 20, 250, "Main (a caller)", [], ["schedule(spec) / cancel(id)", "scheduleAll(batch)", "start() / shutdown()"])
put("spec", 10, 150, 250, "JobSpec", ["id, task", "delayMs or atMs", "trigger, retry, misfire", "priority, after"],
    ["of(id, task)", "in(ms) / at(epochMs)", "every(t) / retry(r)", "misfire(m) / priority(p)", "after(ids...)"])
put("task", 10, 380, 250, "Task", [], ["run() throws Exception"], "interface")
put("clock", 10, 475, 250, "Clock", [], ["nowMs(): long", "static system(): monotonic"], "interface")
put("manual", 10, 585, 250, "ManualClock", [], ["set(ms) / advance(ms)"])
put("sched", 300, 20, 340, "Scheduler",
    ["byTime: PriorityQueue by dueAt", "ready: PriorityQueue, order handed in", "jobs: Map&lt;id, ScheduledJob&gt;",
     "counts: EnumMap&lt;JobState, int&gt;", "handoff: BlockingQueue to workers", "lock: ReentrantLock, wake: Condition",
     "running, live, workers", "clock: Clock, listeners"],
    ["schedule(spec) / scheduleAll(batch)", "schedule / scheduleAtFixedRate / ...Delay", "cancel(id): boolean",
     "status(id) / counts() / prerequisitesOf(id)", "configure(whichFirst) / addListener(l)",
     "start() / pollDue(now) / runJob(job)", "shutdown() / shutdownNow()", "limitPending(max) / awaitTermination(ms)",
     "private: dispatchLoop, workLoop, finishLocked"])
put("listener", 300, 385, 150, "RunListener", [], ["onRun(r)"], "interface")
put("record", 470, 385, 170, "RunRecord", ["jobId, attempt", "startedAt, finishedAt", "error: null = ok", "then: JobState"], [], "record")
put("job", 680, 20, 250, "ScheduledJob",
    ["id, task, seq", "trigger, retry, misfire", "priority", "state: JobState", "plannedAt, dueAt", "attempts, waitingFor",
     "cancelRequested", "after: List&lt;String&gt;", "dependents: List&lt;ScheduledJob&gt;"], ["recurring(): boolean"])
put("state", 680, 262, 250, "JobState", ["BLOCKED, SCHEDULED, RUNNING", "DONE, FAILED, CANCELLED,", "SKIPPED",
                                         "ALLOWED: state -&gt; next states"], ["isFinal()"], "enum")
put("misfire", 680, 420, 250, "Misfire", ["RUN_ALL, RUN_ONCE, SKIP"], ["place(t, next, ended, now)"], "enum")
put("trigger", 970, 20, 240, "Trigger", ["NONE = -1, ONCE"], ["next(plannedAt, finishedAt)"], "interface")
put("fixed", 970, 125, 240, "FixedRate | FixedDelay", [], ["rate: plannedAt + period", "delay: finishedAt + delay"])
put("retry", 970, 230, 240, "RetryPolicy", ["GIVE_UP = -1, NONE"], ["delayMs(attempts, error)"], "interface")
put("backoff", 970, 335, 240, "ExponentialBackoff", ["baseMs, capMs, maxAttempts", "random: null = no jitter"],
    ["delayMs: base x 2^(n-1), capped"])
edges = [
 ln(B["caller"]["r"], (300, B["caller"]["r"][1]), "assoc", "calls"),
 ln(B["caller"]["b"], B["spec"]["t"], "assoc", "builds"),
 ln(B["spec"]["b"], B["task"]["t"], "assoc"),
 ln(B["manual"]["t"], B["clock"]["b"], "inherit"),
 ln((300, 300), B["clock"]["r"], "inject", "", [(280, 300), (280, B["clock"]["r"][1])]),
 ln((640, 110), (680, 110), "compose"),
 ln((375, B["sched"]["b"][1]), B["listener"]["t"], "notify", "after unlock"),
 ln((555, B["sched"]["b"][1]), B["record"]["t"], "assoc", "publishes"),
 ln(B["listener"]["r"], (470, B["listener"]["r"][1]), "assoc"),
 ln(B["job"]["b"], B["state"]["t"], "assoc"),
 ln((700, B["job"]["b"][1]), B["misfire"]["l"], "assoc", "", [(700, 240), (665, 240), (665, B["misfire"]["l"][1])]),
 ln((930, 47), (970, 47), "inject"),
 ln((930, 180), B["retry"]["l"], "inject", "", [(950, 180), (950, B["retry"]["l"][1])]),
 ln(B["fixed"]["t"], B["trigger"]["b"], "inherit"),
 ln(B["backoff"]["t"], B["retry"]["b"], "inherit"),
]
UMLSVG = uml_svg(1230, 700, edges, legend_y=675)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values; &laquo;record&raquo; = a bundle of fields that never changes). Middle: its fields, the state it holds. '
 'Bottom: its methods. <b>The arrows.</b> Hollow triangle = implements. Filled diamond = owns: the scheduler owns every '
 'ScheduledJob. Plain arrow = references: a caller builds a JobSpec and calls the scheduler; a job points at its state '
 'and its Misfire answer; the scheduler publishes a RunRecord for each attempt. Dashed green = handed in: the clock '
 'through the constructor, a job\'s Trigger and RetryPolicy on its JobSpec, and the priority rule (a JDK Comparator, so '
 'not drawn) through <code>configure()</code>. Dotted blue = notifies: the one call the scheduler makes after it has '
 'released the lock. <b>Where state lives:</b> a ScheduledJob holds one job\'s facts (its times, state and attempts, how '
 'many prerequisites it still waits for, and who waits for it); the Scheduler holds everything shared (the two heaps, the '
 'map, the counts, the hand-off queue and the lock), and it is the only class that changes a job\'s state. The '
 'dispatcher and the workers are not boxes: they are loops inside Scheduler (<code>dispatchLoop</code>, '
 '<code>workLoop</code>). The extensions on page 05 (Cron, SkipHolidays, Spread, Aging, TimeoutTask, Placement, JobStore, '
 'RunHistory) plug into these same interfaces and are not drawn.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it does and what it guarantees. Read only those first for the shape, then the bodies; '
 'start with <code>dispatchLoop</code> and <code>finishLocked</code>, which are the whole interview. Each copy button '
 'copies that whole file. Below Main.java: Extensions.java (every follow-up\'s reference code, with an '
 '<code>ExtDemo</code> main that runs all of it) and FailureTests.java (sixteen claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT +
 '</div>Before typing, write your six to eight clarifying questions; then type in the order of Main.java: Task and Clock; '
 'Trigger with FixedRate and FixedDelay; RetryPolicy with ExponentialBackoff; JobState with its ALLOWED table; JobSpec and '
 'ScheduledJob; then the Scheduler: the two heaps, the map and the lock, <code>schedule</code>, <code>pollDue</code>, the '
 'dispatcher loop with <code>awaitNanos</code> and the signal, the worker loop and <code>runJob</code>, '
 '<code>finishLocked</code> in its order, <code>cancel</code>, <code>shutdown</code>; last, a main with the race. If the '
 'clock runs out, the one thing that must exist is schedule with a delay, the dispatcher loop that decides and waits under '
 'the lock and is woken by an earlier job, workers that run jobs outside the lock, and cancel decided under the lock. '
 'Retries, recurring jobs and prerequisites come next, in that order.</div></div>')

race_main = src[src.index("        // the race: 16 threads"):src.rindex("    }\n}")].rstrip() + "\n"

PATTERNS = ('// Strategy: rules behind one-method interfaces, handed in, never built\n'
 'interface Trigger { long next(long plannedAt, long finishedAt); }\n'
 'interface RetryPolicy { long delayMs(int attempts, Exception error); }\n'
 'scheduler.configure(Aging.comparator(10_000));            // which due job goes first\n\n'
 '// Decorator: wrap a rule instead of replacing it\n'
 'Trigger t = Spread.of("nightly-report", new SkipHolidays(Cron.parse("30 9 * * 1-5", IST), IST, holidays), 600_000);\n\n'
 '// Observer: told after the unlock; the scheduler never knows who listens\n'
 'interface RunListener { void onRun(RunRecord r); }\n'
 'publish(events);                                          // AFTER lock.unlock()\n\n'
 '// State: the life as a table; any other move throws\n'
 'if (!JobState.ALLOWED.get(j.state).contains(to)) throw new IllegalStateException(...);\n\n'
 '// Command: a job\'s work as an object: stored, run later, run again\n'
 'interface Task { void run() throws Exception; }\n\n'
 '// Builder: six optional settings, one readable line\n'
 'JobSpec.of("backup", task).in(300_000).retry(new ExponentialBackoff(1_000, 60_000, 5, rnd)).after("snapshot");\n\n'
 '// Producer-consumer: the dispatcher puts, N workers take\n'
 'handoff.addAll(due);             // dispatcher, under the lock\n'
 'ScheduledJob j = handoff.take(); // worker, then runJob(j) outside the lock\n')

SOLID = ('// S: one reason to change each\n'
 'final class ScheduledJob { /* one job\'s facts */ }    record FixedRate(long periodMs) implements Trigger { /* when next */ }\n'
 'final class Scheduler { /* the heaps, the lock, the flow */ }\n'
 '// O: new behaviour = new classes; Scheduler never opened\n'
 'spec.every(new SkipHolidays(Cron.parse("30 9 * * 1-5", IST), IST, holidays));\n'
 '// L: any trigger drops in; nobody asks which one it is\n'
 'long next = j.trigger.next(j.plannedAt, finishedAt);\n'
 '// I: one method per interface, so a fake is a lambda\n'
 'Task failing = () -> { throw new IOException("disk full"); };    Clock frozen = () -> 0L;\n'
 '// D: depend on interfaces; implementations handed in, tests hand in fakes\n'
 'Scheduler s = new Scheduler(4, new ManualClock(0));    s.configure(Scheduler.BY_DUE);\n')

FU = [
("A job due in 10 s is being waited on. A job due in 1 s arrives. Show that it runs at 1 s, not 10, and say what a spurious wakeup does.",
 "non-functional", 10,
 "The dispatcher never sleeps on stale information. <code>dispatchLoop</code> holds the lock while it takes whatever is "
 "due, works out how long until the earliest job, and calls <code>awaitNanos</code> with that time; await lets go of the "
 "lock only once the thread is waiting, and takes it back before it returns. <code>schedule()</code> adds the new job "
 "under the same lock, and if the new job is now the head of the time heap it signals. So the signal can only arrive "
 "while the dispatcher is waiting: it wakes, sees the 1 s job, and sleeps again for one second. A spurious wakeup (await "
 "returning although nobody signalled, which Java allows) and a timeout both go back to the top of the same loop, which "
 "starts nothing that is not due. Test 2 puts the dispatcher to sleep towards a 5 s job, adds a 50 ms job, and measures "
 "about 55 ms; with the signal line deleted, it waits the full 5 seconds and fails.",
 cut(src, "/** How long the dispatcher may sleep", "/** A worker thread: take a job") + "\n"
 + cut(src, "/** Into the time heap as SCHEDULED", "* Move a job to a final state") + "\n"
 + T("        // 2. the lost wakeup", "        // 3. cancel")),

("Fixed rate or fixed delay: what is the difference, and what happens when a run takes longer than its period?",
 "functional", 10,
 "Both are Trigger classes of one line each. <code>FixedRate</code> returns the planned start plus the period, so a job "
 "planned for 10:00:00, 10:00:10 and 10:00:20 keeps that rhythm however long each run takes. <code>FixedDelay</code> "
 "returns the end of the last run plus the delay, so a slow run pushes every later run back (test 6: starts at 0, 1000, "
 "2000 against 10000, 11300, 12600 with 300 ms runs). In <code>finishLocked</code> a recurring job is put back into the "
 "time heap only after its run has ended, so two runs of one job can never overlap, even with idle workers (test 7: "
 "25 ms runs every 5 ms, never two at once). A planned time that has already passed when the run ends is a misfire, and "
 "the job's Misfire decides: RUN_ALL runs every missed slot back to back (what the JDK does), RUN_ONCE runs one late run "
 "for all of them, SKIP waits for the next slot. Time itself comes from the injected Clock: in production "
 "<code>Clock.system()</code>, which reads System.nanoTime (monotonic: it never jumps when NTP, the service that "
 "corrects a machine's clock, moves the wall clock), and in tests a ManualClock that the job itself moves "
 "forward, so nothing sleeps.",
 cut(src, "* Fixed rate: every periodMs", "/** How long to wait before the next attempt") + "\n"
 + T("        // 7. a run longer", "        // 8. retries")),

("Prove it is thread-safe: 16 threads submit at once, 8 workers run them. Nothing lost, nothing run twice, never 9 at once.",
 "non-functional", 10,
 "Main's race does exactly that. Sixteen threads wait on one latch (a gate that opens for all of them at once), then each "
 "submits 500 jobs due within the next 20 ms, and eight workers run them. Every job adds one to its own counter and "
 "tracks how many jobs are running at that moment. At the end, every one of the 8,000 counters is exactly 1, the most "
 "running at one moment is 8 and never 9, and the DONE count is 8,000. It holds because every change to the heaps, the "
 "map and the states happens under the one lock, and the dispatcher hands out a job only while fewer jobs are running "
 "than there are workers. Test 5 checks the bound from the other side: 40 jobs of 20 ms on 4 workers reach 4 at once, so "
 "the pool is really used.",
 race_main + "\n" + T("        // 5. a fixed pool", "        // 6. fixed rate")),

("Two prerequisites finish in the same millisecond, and another one fails. What happens to the jobs waiting on them?",
 "functional", 10,
 "Each job keeps <code>waitingFor</code>, the number of prerequisites not yet DONE, and each prerequisite keeps its "
 "<code>dependents</code>. When a job ends, <code>endLocked</code> settles its dependents inside the scheduler's lock. On "
 "DONE it counts each one down, and the finish that brings a count to zero moves that job to SCHEDULED. Two builds "
 "finishing in the same millisecond are taken one after the other by the lock, so deploy is queued exactly once; the "
 "test releases eight prerequisites through a barrier, thirty times, and deploy runs once each time, after all eight. On "
 "FAILED, CANCELLED or SKIPPED it skips every dependent and everything behind them, breadth first, and records why; a job "
 "submitted later that waits for a failed job is SKIPPED at once (test 12). Jobs that wait for nothing are untouched.",
 cut(src, "* Move a job to a final state, then settle", "/** The one place a state changes") + "\n"
 + T("        int rounds = 30", "        // 12. a failed prerequisite")),

("A batch of jobs forms a loop. Refuse it, and print the loop. Then: what must finish, in what order, before job X can run?",
 "functional", 10,
 "<code>scheduleAll</code> checks before it creates anything. <code>findCycle</code> runs Kahn's algorithm over the "
 "batch: count, for each job, its prerequisites inside the batch, then keep removing jobs whose count is zero and counting "
 "down the jobs waiting for them. If every job was removed there is no loop. If some are left, each of them still waits "
 "for another one left, so walking \"waits for\" links from any of them must come back to a job already seen, and that "
 "stretch is the loop: \"x -> z -> y -> x\". The batch is refused whole, so w, which was fine, is not kept either. "
 "Brex's completion plan reads the same graph the other way: a depth-first walk from X that writes a job down only after "
 "everything it waits for, which gives yoga, coffee, toast, brainstorm. Both use their own stack and queue rather than "
 "recursion, so a 20,000-job chain cannot overflow the call stack (test 13).",
 cut(src, "* Kahn's algorithm over the batch", "// ---------------------------------------------------------------- cancel, and questions")
 + "\n" + X("completion plan")),

("The job throws. Retry it up to five times with backoff, then give up. And the worker must survive.",
 "functional", 10,
 "<code>runJob</code> runs the task with no lock held and catches everything. An exception is a failed attempt, and so "
 "is an Error such as StackOverflowError (wrapped), so a worker thread never dies and its slot is never lost; test 9 "
 "proves it with a single worker. <code>finishLocked</code> then asks the job's RetryPolicy how long to wait. "
 "<code>ExponentialBackoff</code> answers base, twice base, four times base, up to a cap; with jitter, half of each wait "
 "is random, so a thousand jobs that failed at the same moment do not all retry in the same millisecond. After "
 "maxAttempts it answers GIVE_UP. A retry goes back into the time heap at end + wait and keeps its planned slot, so a "
 "fixed-rate job's rhythm does not shift. When the policy gives up, a one-shot job is FAILED and its dependents are "
 "skipped, while a recurring job records the failed run and carries on with its next one. The rules themselves run in a "
 "try block too: a Trigger or RetryPolicy that throws ends only its own job, FAILED, instead of leaving it stuck RUNNING "
 "(test 9). Test 8 shows four attempts at 0, 100, 300 and 700 ms, then FAILED.",
 cut(src, "/** Run one handed-out job on the calling thread", "/** Into the time heap as SCHEDULED") + "\n"
 + cut(src, "* Exponential backoff with jitter", "// ================================================================ a job's life")),

("Cancel a job. What if the dispatcher is taking it at that very moment? What if it is already running?",
 "functional", 5,
 "<code>cancel(id)</code> and the dispatcher both decide under the scheduler's lock, so they cannot interleave: one of "
 "them goes first. If cancel goes first, the job is still BLOCKED or SCHEDULED; it becomes CANCELLED, the jobs waiting "
 "for it are skipped, and cancel returns true. The job stays in its heap and the dispatcher drops it when it reaches the "
 "top (lazy removal, because <code>PriorityQueue.remove</code> is a scan). If the dispatcher goes first, the job is "
 "already RUNNING; cancel returns false and sets <code>cancelRequested</code>, so this run finishes but no retry and no "
 "next run follow. Test 4 races a cancelling thread against the dispatcher over 2,000 jobs: every job either ran once or "
 "was cancelled, never both and never neither, and both sides won some of the races.",
 cut(src, "* Cancel a job. True if it had not started", "/** A job's state, or null") + "\n"
 + T("        // 4. cancel racing", "        // 5. a fixed pool")),

("Several jobs are due and every worker is busy. Highest priority first. Won't a low-priority job starve?",
 "functional", 5,
 "When their time comes, due jobs move from the time heap to a second heap, <code>ready</code>, whose order is a "
 "Comparator the scheduler is handed; the default is higher priority, then earlier due time, then first come. So with "
 "one free worker the priority-9 job goes before a priority-1 job that was due earlier (test 10). Plain priority can "
 "starve: a steady stream of high-priority jobs keeps a low one waiting for ever. Aging is a different comparator, one "
 "line long: order by due time minus priority times a step, so every step of waiting is worth one level. Two waiting "
 "jobs age at the same speed, so their order never changes while they wait, which keeps the heap valid. With a 10 s "
 "step, a priority-1 job due 30 s ago goes before a priority-3 job due now, and nothing waits for ever.",
 cut(src, "/** Order of the time heap", "/** The stop sign a worker takes") + "\n"
 + cut(src, "/** Hand in the rule for which due job goes first", "/** Subscribe a listener") + "\n" + X("aging")),

("Swiggy: 'design your own cron: a unix command and an epoch time'. Then: weekdays at 09:30 IST, no holidays, not all 5,000 at once.",
 "twist", 10,
 "The epoch time is <code>JobSpec.at(epochMs)</code>, already in Main; a time already past runs at once. The command is a "
 "Task like any other: <code>CommandTask</code> starts it as its own process, waits up to a time limit and kills it if it "
 "overruns (a process can be killed, a thread cannot), and treats a non-zero exit code as a failed attempt, so retries "
 "apply. The recurring part is a Trigger. <code>Cron</code> parses a crontab line (minute, hour, day of month, month, "
 "day of week) into five sets of allowed "
 "values and walks forward from the last planned start, skipping a whole month, day or hour at a time, in the job's own "
 "time zone, so 09:30 IST stays 09:30 IST. The rule change is two decorators around it, with nothing edited: "
 "<code>SkipHolidays</code> moves a run off a holiday, and <code>Spread</code> shifts every run by a fixed offset taken "
 "from the job's id (what Jenkins calls H), which spreads 5,000 jobs over ten minutes without letting any of them drift.",
 X("cron, holidays and spreading")),

("Persist it, and run the scheduler on three machines without losing or double-running a job.",
 "twist", 10,
 "The jobs go into a table behind a repository interface, <code>JobStore</code>, and every scheduler machine polls it "
 "for due rows. Taking a job is one conditional UPDATE: set the owner and a lease (a claim that expires) only where the "
 "last lease has already run out. One row changed means this machine won; zero means another did. That is the "
 "database's compare-and-set, doing what the lock did inside one process. Finishing is conditional too: DONE only if "
 "this machine still holds the lease. A machine that dies mid-job simply lets its lease expire, and another machine runs "
 "the job again, so a job runs at least once, never exactly once, and every job must be idempotent (safe to run twice). "
 "The demo sends 300 emails through three instances with one crash: 301 runs, and the effect table keyed by job id holds "
 "300. After a restart, missed recurring runs go through the same Misfire rule: an hour down with a 10 s job means 360 "
 "runs back to back, one run now, or none.",
 X("persistence and many instances")),

("Not every worker can run every job: some need a GPU or 100 GB of RAM. And at most two report jobs may run at once.",
 "twist", 10,
 "Workers stop being identical, so placement becomes a decision made under one lock, like dispatch. "
 "<code>Placement</code> keeps each machine's capabilities and its free CPU and RAM, and the waiting jobs in priority "
 "order. Each waiting job goes to the fitting machine that wastes least: fewest capabilities it does not need, then "
 "least CPU and RAM left over, so the GPU machine stays free for GPU work. A job that fits nowhere yet waits, and smaller "
 "jobs behind it may go first (backfilling); a job that fits no machine at all is refused at submit. When a job ends, "
 "its resources come back and placement runs again. The per-type limit is simpler: <code>Bulkheads</code> gives each "
 "type its own small Scheduler with that many workers, so ten report jobs run at most two at a time and can never take "
 "the payment jobs' workers.",
 X("machines with capabilities")),

("Why not just use ScheduledThreadPoolExecutor? What does the JDK already give you?",
 "design", 5,
 "In production, use it. ScheduledThreadPoolExecutor is this same design: a heap of tasks under one lock, a Condition "
 "to wait for the head, and worker threads (its workers take turns being the one that waits for the head, instead of a "
 "separate dispatcher). DelayQueue gives the heap and the wait on their own: its <code>take()</code> blocks until the "
 "head is due and wakes early for an earlier item, which is enough for the 25-line <code>DelayQueueScheduler</code> "
 "below. Interviewers ask you to build it anyway because the wait-and-signal protocol is the question, and because the "
 "parts around it are not in the JDK: prerequisites, retries with backoff, priority among due jobs, misfire rules. Know "
 "its traps too. A fixed-rate task that throws is cancelled silently, with the exception visible only through its "
 "future (the demo: two runs, then nothing), and java.util.Timer runs every task on one thread, which dies at the first "
 "exception. This scheduler records the failure and keeps the schedule.",
 X("what the JDK already gives you")),

("Shut it down: let queued work finish, or stop now. What happens to a job that is sleeping, or hangs for ever?",
 "non-functional", 10,
 "<code>shutdown()</code> refuses new jobs and cancels the recurring ones, which would otherwise never end; one-shot "
 "jobs already accepted still run at their time, with their retries and prerequisites. When nothing is left, the "
 "dispatcher leaves its loop and puts one stop sign per worker on the hand-off queue. <code>shutdownNow()</code> "
 "cancels every job that has not started, including whole chains waiting on prerequisites, returns their ids, and "
 "interrupts the workers; a job that is sleeping, waiting or blocked on I/O gets InterruptedException and ends "
 "CANCELLED (test 15: done in milliseconds). Java cannot "
 "force a thread to stop, so a job that never blocks and never checks for interrupts runs to its end. A per-job time "
 "limit has the same limit: <code>TimeoutTask</code> arms a watchdog (another scheduler) that interrupts the worker "
 "when time is up, and a small lock makes sure a late watchdog cannot interrupt the next job on that worker. Code that "
 "must really be killable runs as a process.",
 cut(src, "* Graceful: refuse new jobs.", "// ================================================================ a demo") + "\n" + X("timeouts")),

("Ten thousand jobs a second through one lock: does it scale? And what if jobs arrive faster than the workers run them?",
 "non-functional", 5,
 "Say the numbers. Measured here, one job costs about one and a half microseconds of lock for all three visits, with "
 "250,000 jobs in the heaps, so ten thousand jobs a second is 15 ms of lock in every second: 1.5% busy. The workers run "
 "out long before: ten thousand jobs of 4 ms each need forty workers, not a better lock. Until there are enough, jobs "
 "pile up, and back-pressure keeps that safe: a worker gets a job only when it is free, and <code>limitPending(max)</code> "
 "makes schedule() throw RejectedExecutionException once max jobs are unfinished, an error the caller can see and retry "
 "later instead of an OutOfMemoryError (test 5). If submitting threads really "
 "do queue on the lock, rung one is K schedulers, each with its own lock, heaps and dispatcher, a job going to the shard "
 "hash(id) mod K. It has two costs: priority holds only inside a shard, and a batch with prerequisites must go to one "
 "shard, routed by one key. Rung two is a timing wheel (a bucket for each tick of time, the Kafka and Netty answer for "
 "millions of timers), and rung three is many machines on one jobs table.",
 cut(src, "* Back-pressure at the door", "/** Launch the dispatcher") + "\n" + X("sharding")),

("The dashboard asks 'how many jobs are waiting, running, failed?' and 'what happened to job X?' a thousand times a second.",
 "non-functional", 5,
 "<code>counts()</code> copies seven numbers that <code>move()</code> keeps right on every state change, so it never "
 "counts anything; <code>status(id)</code> is one map lookup. Both hold the lock for well under a microsecond, so a "
 "thousand calls a second cost about a millisecond of lock. The history is a listener, so the scheduler does not change: "
 "<code>RunHistory</code> keeps the last N run records and the latest one per job, both bounded so memory cannot grow for "
 "ever, and it has its own small lock because listeners are called from many worker threads at once, after the "
 "scheduler's lock is released. The same stream of records feeds metrics, or a pager on FAILED.",
 cut(src, "/** A job's state, or null for an unknown id", "// ---------------------------------------------------------------- the dispatcher and the workers")
 + "\n" + X("history")),

("Which pattern is where, and why did each one earn its place?", "design", 5,
 "Each one is what a move produced. Strategy is move 3: when a job runs next, how it is retried and which due job goes "
 "first are rules that change, so each sits behind a one-method interface the scheduler is handed. Decorator is "
 "SkipHolidays and Spread, which wrap a Trigger instead of replacing it. Observer is move 4's rule that listeners are "
 "told after the lock, never inside it. State is move 6: the ALLOWED table and <code>move()</code>. Command is the Task "
 "itself: work packed as an object that can wait, run later and run again. Builder is JobSpec, because a job has six "
 "optional settings. Producer-consumer is the hand-off queue between the dispatcher and the workers. Two you should not "
 "claim: no Singleton, because every test builds its own scheduler, and no Factory until schedules arrive as text.",
 PATTERNS),

("Which SOLID letter is where in this code?", "design", 5,
 "S: each class has one reason to change. A ScheduledJob changes when a job's facts change, a Trigger when the rhythm "
 "rule does, the Scheduler when the flow or the locking does. O: cron, holidays, spreading and aging were each a new "
 "class, and Scheduler was never opened. L: <code>j.trigger.next(...)</code> works for every Trigger, and nothing asks "
 "which one it got. I: Task, Clock, Trigger, RetryPolicy and RunListener each have one method, so a fake for a test is "
 "one lambda. D: the scheduler depends on those interfaces and is handed the implementations, which is exactly why a "
 "test can hand it a clock that says \"Monday 09:30\" and a task that always throws.",
 SOLID),

("Misfire is an enum and Trigger is an interface. Why the difference? And where would a Factory pay?", "design", 3,
 "An enum when the list is closed and each answer is data; an interface when new kinds keep coming and each carries its "
 "own logic. Misfire has exactly three answers to one question (run all, run once, skip), and the logic for all three is "
 "ten lines in one method, so an enum is enough. Triggers keep coming (fixed rate, fixed delay, a cron line, holidays, "
 "spreading, business days), and each works out time in its own way, so Trigger is an interface and each kind a class. "
 "JobState is an enum for the same reason as Misfire, with the ALLOWED table as its data. A Factory pays once schedules "
 "stop being objects in code and arrive as text, from a config file or an API: <code>Triggers.parse</code> turns "
 "\"every 10s\" or \"cron 30 9 * * 1-5 Asia/Kolkata\" into the right Trigger, and a new kind is one more case there, "
 "not a change in every caller.",
 cut(src, "* What happens to planned runs of a recurring job that were missed", "/** How long to wait before the next attempt")
 + "\n" + X("schedules from text")),
]

build(dict(
    slug="job-scheduler", title="Job Scheduler (delayed and recurring jobs on worker threads)",
    subtitle="LLD &middot; concurrency &middot; Java &middot; OpenJDK 21 &middot; demo, 16 failure tests and a 16-thread race pass",
    problem_body=PROBLEM_BODY,
    derivation_lead=("Run these on any LLD (parking lot, rate limiter, a thread pool) and the class diagram, the lock, the "
                     "tests, the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen "
                     "up front, and nothing is named before the move that produced it. Here, moves 4, 5 and 6 each end "
                     "with a second part for prerequisites (jobs that wait for other jobs): the race, the shapes and the "
                     "life."),
    moves=MOVES,
    uml_svg=UMLSVG, how_to_read=HOW_TO_READ,
    code_intro=CODE_INTRO,
    files=[("Main.java", src), ("Extensions.java", ext), ("FailureTests.java", tests)],
    test_class="FailureTests",
    implement_card_html=IMPLEMENT,
    followups=FU,
))
