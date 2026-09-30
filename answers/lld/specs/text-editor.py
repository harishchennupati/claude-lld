# Text editor LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"text-editor/Main.java").read_text()
ext   = (H/"text-editor/Extensions.java").read_text()
tests = (H/"text-editor/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("type",   30,  [("a keystroke arrives", "at the caret, or over a selection"),
                         ("the change becomes a command", "it carries its own undo"),
                         ("under one lock, in order", "buffer, then history, then version"),
                         ("then tell the views", "after the unlock, never inside it")]),
        ("ctrl+Z", 165, [("the user presses undo", "the last STEP, not a version"),
                         ("pop the top command", "one step, however many edits"),
                         ("cmd.undo(doc)", "the exact characters come back"),
                         ("push it onto redo", "redo is execute() again")]),
        ("cut / paste /\nreplace all", 255, [("a range, or 40 hits", "one selection, or the whole file"),
                                            ("ONE command", "or one made of commands, in order"),
                                            ("the same apply(), same lock", "the editor gains no method"),
                                            ("one ctrl+Z undoes all of it", "children reversed, last first")])]
for lab, y, boxes in rows:
    for j, part in enumerate(lab.split("\n")):
        pf += _tx(165, y+31 + (j*17 if "\n" in lab else 0) - (8 if "\n" in lab else 0), part, "var(--acc)", 12.5, "end")
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == (1 if y == 255 else 2)))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M815 84 V95", dash=True) + _bx(650, 95, 330, 40, "refused: nothing is recorded", "", dash=True)
pf += _tx(165, 356, "read", "var(--acc)", 12.5, "end")
pf += _tx(175, 356, "at any moment, and without taking the lock: what is the text?  which version is on screen?  can I undo, and what would it undo?",
          "var(--text)", 12, "start")
pf += _tx(615, 395, "one writer at a time on the buffer: the characters, the history and the version move together, or none of them move", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 410, pf)

# one minute of typing, replayed
pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("10:04:01  types \"hello\"", ["five keystrokes, 40 ms apart", "the rule fuses them into ONE step",
                                    "version 5, undo depth 1"], True),
      ("10:04:03  pastes 4 KB", ["one insert, kind = PASTE", "the wrapper refuses to merge it",
                                 "version 6, undo depth 2"], False),
      ("10:04:09  ctrl+Z", ["the 4 KB comes out in one piece", "text is \"hello\" again",
                            "version 7, redo depth 1"], True),
      ("10:04:11  types \" world\"", ["a new edit clears the redo stack", "the 4 KB is gone, on purpose",
                                      "version 8, undo depth 2, redo 0"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 112, t, lines, acc=acc)
P_EX = _mv(1230, 188, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Insert text at an offset and delete a range; a caret, and a selection you can drag either way.</li>
<li>Every change goes through ONE entry point that mutates, records and notifies &mdash; there is no second way to move a character.</li>
<li>Undo reverses the last step; redo re-applies it; a new edit throws the redo branch away.</li>
<li>Consecutive keystrokes collapse into word-sized steps under a swappable rule; a paste is always its own step.</li>
<li>Cut, copy and paste, where cutting a selection is one step and one ctrl+Z puts it all back.</li>
<li>Find and replace all &mdash; forty hits, one ctrl+Z.</li>
<li>The Edit menu can ask: can I undo, what would it undo, and which version is on screen.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Under stray threads &mdash; an autosave, a plugin, a macro &mdash; the buffer, the history and the version move together or not at all.</li>
<li>Undo and redo are O(1); an insert at the caret is O(1) amortised however long the document is.</li>
<li>Readers never take the lock: a volatile snapshot plus a version number.</li>
<li>Memory is bounded: the history has a step cap, and undo keeps the change, never a copy of the document.</li>
<li>The storage and the grouping rule are swappable without reopening the editor or the history.</li>
<li>Nothing half-done: an edit that throws leaves the text, the history and the caret exactly as they were.</li>
<li>One document, one process, in memory: no files, no network, no formatting (say it; they are follow-ups).</li></ul></div></div>
'''

PROMPT = ('"Design a text editor. Typing, deleting, cut and paste, and the part I actually care about &mdash; undo and '
          'redo that a user can trust. One document, in memory. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Somebody types a character and it appears; they press '
 'ctrl+Z and it disappears. That second sentence is the whole design. If ctrl+Z means "go back to the previous '
 'version of the document", you are copying the whole file on every keystroke, and a ten-megabyte file kills you. So '
 'ctrl+Z has to mean "reverse the last <i>change</i>", which turns a change into a thing you can hold: an object that '
 'knows what it did and how to take it back. Five keystrokes should be one ctrl+Z but a four-kilobyte paste should '
 'not, so something has to decide when two edits are really one step. The document is also being watched &mdash; a '
 'renderer repaints, an autosave writes, a syntax highlighter re-colours &mdash; and none of them may sit in the way '
 'of a typist. The one thing that must always be true: the characters, the undo history and the version number agree. '
 'A buffer that moved while the history did not is the bug where the next ctrl+Z deletes the wrong characters, and '
 'nobody notices until the document is ruined.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that types, deletes, undoes, redoes and prints. The interviewer is watching for, in this order: '
 'the questions you ask before typing (plain or rich text, and how big the document gets, are the first two); which '
 'classes exist and which one owns the characters; an edit end to end from keystroke to repaint; what happens when a '
 'second thread touches the document while the first is half way through an edit; where the rule that will change '
 '(when do edits group?) lives, so a new rule is a new class and not an edit; and what the system looks like after an '
 'edit that threw. Then the twists: replace-all in one ctrl+Z, macros, drawing lines 4000 to 4050 of a huge file, a '
 'file too big for a StringBuilder, rich text, persistence, and two people at once.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Plain text or rich text?</td><td>Plain text; styles are a follow-up</td><td>Whether "bold this" is also a command on the undo stack (moves 1, 12)</td></tr>'
 '<tr><td>How large can one document get?</td><td>Up to about a megabyte today, more later</td><td>The storage behind an interface: StringBuilder, gap buffer, piece table (moves 3, 5)</td></tr>'
 '<tr><td>Is undo per document or per author?</td><td>One author, one document</td><td>A stack, not a transform. Two authors is a different problem entirely (moves 6, 12)</td></tr>'
 '<tr><td>Undo twice, then type. Is the abandoned branch recoverable?</td><td>No: linear history</td><td>Two stacks rather than a history tree, and a new edit clears redo (move 6)</td></tr>'
 '<tr><td>What closes an undo step &mdash; a pause, a space, a caret move, a paste?</td><td>A pause or a word boundary; a paste never merges</td><td>The grouping rule behind a one-method interface, and a wrapper that polices it (move 3)</td></tr>'
 '<tr><td>How deep is the history, and bounded by what?</td><td>A cap on steps, not on bytes</td><td>The eviction rule, and why "unsaved" cannot mean "the undo stack is empty" (moves 5, 6)</td></tr>'
 '<tr><td>Who calls this &mdash; one UI thread, or also an autosave and plugins?</td><td>More than one thread</td><td>Whether a lock is needed at all, and what it must span (moves 4, 7)</td></tr>'
 '<tr><td>Two people editing the same document?</td><td>Out of scope, named</td><td>Operational transformation or a CRDT, and a stack cannot express either (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One minute of typing, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> undo reverses the last change, not the last version, so a change is an '
 'object that carries its own inverse; a delete keeps the characters it removed, which is what makes it reversible at '
 'all; history is linear, so typing after an undo throws the branch away on purpose; the storage and the grouping rule '
 'are both handed in; one document, one process, in memory. Named as out of scope: rich text, files on disk, '
 'collaborative editing &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a USER types into a DOCUMENT; every EDIT knows its own inverse; an UNDO STACK and a REDO STACK hold them; a CLIPBOARD; VIEWS watch", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 180, "Document", "characters + a caret", 1), (228, 175, "TextBuffer", "how they are stored", 1),
                          (421, 165, "Selection", "two ints: a record", 1), (604, 185, "EditCommand", "its own undo inside it", 1),
                          (807, 175, "UndoManager", "two stacks and a cap", 1), (1000, 200, "MergePolicy / View", "no state: interfaces", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a rule, or somebody who only listens", "var(--muted)", 11)
m1 += _tx(615, 209, "and notice what is NOT a class: a version of the document. Keeping one per keystroke is the mistake this whole design exists to avoid.", "var(--acc)", 11)
MV[1] = _mv(1230, 222, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("put characters in at an offset", "TextBuffer  (owns the characters)", "buf.insert(at, s)"),
                                       ("remember how to take them out again", "EditCommand  (owns its own inverse)", "cmd.undo(doc)"),
                                       ("decide if two keystrokes are one step", "MergePolicy  (owns nothing: pure)", "policy.merge(prev, next)"),
                                       ("type a character", "Editor  (owns doc + history + lock)", "editor.type(\"h\")")]):
    y = 22 + k*52
    m2 += _bx(30, y, 340, 42, verb, "the verb") + _ar("M370 %s H430" % (y+21), True)
    m2 += _bx(430, y, 390, 42, cls, "the class whose state it touches", acc=True) + _ar("M820 %s H880" % (y+21), True)
    m2 += _bx(880, y, 320, 42, meth, "the method")
m2 += _tx(615, 248, "a verb whose state is spread over two classes goes to the class that owns both: the Editor becomes the orchestrator", "var(--muted)", 11)
m2 += _tx(615, 267, "and REDO is not a new verb: it is execute() again, which is why the contract says every command must be repeatable", "var(--acc)", 11)
MV[2] = _mv(1230, 280, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 62, 220, 90, "Editor", "constructor + configure(...)", acc=True)
for k, (t, sub, impl) in enumerate([("TextBuffer", "how characters are stored", "StringBuilderBuffer / GapBuffer / PieceTableBuffer"),
                                    ("MergePolicy", "when two edits are one step", "TypingBurstMergePolicy / NoMergePolicy"),
                                    ("EditListener", "renderer, autosave, plugin", "ConsoleRenderer, Autosave, Highlighter, a lambda")]):
    y = 26 + k*60
    m3 += _ar("M250 107 H330 V%s H400" % (y+21), True, True) + _bx(400, y, 290, 42, t, sub, dash=True)
    m3 += _bx(750, y, 450, 42, impl, "the classes that can be handed in") + _ar("M750 %s H690" % (y+21))
m3 += _tx(615, 216, "dashed green = handed in. The Editor never builds one, so a piece table for a ten-megabyte file is a new class and one changed line", "var(--muted)", 11)
m3 += _tx(615, 236, "and one rule wraps the others: PasteIsItsOwnStep(policy) adds \"only plain typing may ever merge\" to EVERY grouping rule, including the ones written next year", "var(--acc)", 11)
MV[3] = _mv(1230, 249, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 28, 200, 44, "the typing thread", "buffer moves, history next") + _bx(30, 112, 200, 44, "an autosave / a plugin", "reads text() in the gap")
m4 += _bx(360, 70, 200, 44, "the document", "5 chars, history says 4", acc=True)
m4 += _ar("M230 50 H360 V70") + _ar("M230 134 H360 V114") + _tx(295, 38, "writes", "var(--muted)", 10.5) + _tx(295, 162, "reads", "var(--muted)", 10.5)
m4 += '<rect x="600" y="18" width="300" height="144" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(750, 43, "the gap", RED, 12) + _tx(750, 68, "the buffer moved, the history", RED, 11) + _tx(750, 88, "did not: the next ctrl+Z now", RED, 11) + _tx(750, 108, "deletes the wrong characters", RED, 11)
m4 += _tx(750, 140, "fix: all four as ONE step", "var(--text)", 11)
m4 += _bx(930, 40, 270, 100, "Editor.lock", "mutate + record + version + publish", acc=True)
m4 += _tx(1065, 165, "the lock lives where the shared state lives", "var(--muted)", 10.5)
m4 += _tx(1065, 185, "readers take no lock: a volatile snapshot", "var(--muted)", 10.5)
m4 += _tx(615, 210, "the invariant spans a char array and two deques, so there is no single word to compare-and-swap: a lock here is honest, not lazy", "var(--muted)", 11)
MV[4] = _mv(1230, 223, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("insert at the caret, again and again?", "char[] with a movable hole (gap buffer)", "O(1) amortised"),
                                      ("what do I undo next?", "ArrayDeque&lt;EditCommand&gt;, push/pop at the head", "O(1)"),
                                      ("what do I redo next?", "a second ArrayDeque, cleared by every new edit", "O(1)"),
                                      ("what is on screen right now?", "volatile String snapshot + AtomicLong version", "O(1), no lock"),
                                      ("what does the Edit menu say?", "the top k labels off the undo stack", "O(k)"),
                                      ("where does line 4000 start?", "int[] of line starts, binary search (page 05)", "O(log L)")]):
    y = 18 + k*46
    m5 += _bx(30, y, 350, 38, q, "the question") + _ar("M380 %s H440" % (y+19), True)
    m5 += _bx(440, y, 540, 38, shape, "the shape", acc=True) + _ar("M980 %s H1030" % (y+19), True) + _bx(1030, y, 170, 38, cost, "")
m5 += _tx(615, 314, "the memory bound is the same idea: an undo step stores the CHANGE (an offset and a short string), never a copy of the document,", "var(--muted)", 11)
m5 += _tx(615, 333, "and the step count is capped, so a long session cannot eat the heap. Once a step is evicted, \"back to the original\" is gone: say that out loud.", "var(--muted)", 11)
MV[5] = _mv(1230, 346, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D
for k, (t, sub, acc) in enumerate([("CLEAN", "both stacks empty", 0), ("CAN UNDO", "edits, none undone", 1), ("BOTH", "undone, redo waiting", 1)]):
    m6 += _bx(30 + k*175, 28, 160, 44, t, sub, acc=bool(acc))
    if k < 2: m6 += _ar("M%s 50 H%s" % (190 + k*175, 205 + k*175), True)
m6 += _bx(30, 118, 160, 44, "ALL UNDONE", "only redo is left")
m6 += _ar("M380 72 V118 H190", True) + _tx(300, 112, "undo, undo, undo", "var(--muted)", 10.5)
m6 += _ar("M110 118 V95 H285 V72", True) + _tx(278, 90, "a new edit here CLEARS redo", RED, 10.5, "end")
m6 += '<rect x="560" y="18" width="650" height="192" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(885, 42, "the order inside apply(), and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 take the lock -- once per edit; every public method builds its command inside this same span",
                       "2 cmd.execute(doc) -- the buffer moves, or it throws and nothing else happened",
                       "3 only now history.record(cmd): an undo step for an edit that DID happen",
                       "4 bump the version, publish a fresh snapshot, release the lock",
                       "5 then tell the listeners, each inside a try/catch",
                       "a failed edit leaves the text, the history, the version and the caret untouched;",
                       "a command recorded for an edit that never landed would later delete somebody else's characters"]):
    m6 += _tx(575, 66 + k*21, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
m6 += _tx(615, 232, "the edge where the bugs live: any new edit from BOTH or ALL UNDONE must CLEAR the redo stack. Forget it, and a later redo re-applies an edit at an offset that is gone.", "var(--acc)", 11)
MV[6] = _mv(1230, 245, m6)

# move 7: what is inside the lock, and eight callers at the same instant
m7 = _D + _card(30, 18, 560, 158, "inside the lock: about 2 microseconds on a 20 KB file",
                ["insert into the gap: ~20 ns, no characters move", "push one command onto a deque: ~20 ns",
                 "ask the grouping rule if it fuses: ~50 ns", "bump an AtomicLong: ~10 ns",
                 "copy the document into a snapshot String: ~1.5 us  <-- 95% of it"], acc=True)
m7 += _ar("M590 96 H650", True) + _tx(620, 86, "unlock", "var(--acc)", 10.5)
m7 += _card(650, 18, 550, 158, "outside the lock: milliseconds",
            ["the repaint: ~5 ms, after the unlock", "autosave writing the snapshot: ~3 ms",
             "a syntax highlighter re-tokenising: ~1 ms", "a plugin doing who knows what",
             "the human deciding what to type: seconds"])
m7 += _tx(615, 202, "eight threads append at the same instant (this is the actual test in FailureTests.java)", "var(--text)", 12)
for k in range(8):
    x = 30 + k*148
    m7 += _bx(x, 216, 136, 40, "thread %d" % (k+1), "waits %s us" % ("0" if k == 0 else "%d" % (k*2)), acc=(k == 7))
m7 += _tx(615, 284, "the eighth waits fourteen microseconds and then repaints for five milliseconds: one at a time is true, and nobody can tell.", "var(--muted)", 11)
m7 += _tx(615, 303, "the honest weak spot is the snapshot copy. On a 20 KB file it is 1.5 us; on a 1 MB file it is 60 us; on 10 MB it is the reason for move 8's second rung.", "var(--acc)", 11)
MV[7] = _mv(1230, 316, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="18" width="560" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per document: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a fast typist is 8 keystrokes a second, not 8000",
                       "the locked part of one keystroke on a 20 KB file: ~2 us",
                       "8 x 2 us = 16 microseconds of lock in every second",
                       "that is 0.0016% busy: two writers collide about never",
                       "and the lock is per DOCUMENT, so twenty open tabs never meet"]):
    m8 += _tx(35, 68 + k*25, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 notify and persist outside the lock", "already done: listeners are called after the unlock"),
                              ("2 stop copying the whole document per edit", "publish version + changed range, or a piece table whose snapshot is a view"),
                              ("3 more than one author is not a lock problem", "operational transformation or a CRDT; a stack cannot express it")]):
    m8 += _bx(600, 60 + k*52, 600, 44, t, sub, acc=(k == 0))
m8 += _tx(615, 228, "say the arithmetic before you climb: a lock that is busy sixteen microseconds a second does not need a queue, a striped map or an actor", "var(--muted)", 11)
MV[8] = _mv(1230, 242, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("a new edit after an undo leaves a stale redo stack", "record() clears redo first; test 3: redo returns false, the branch is gone"),
                                ("a delete that did not keep what it removed", "the command stashes it on execute; test 2: undo restores the exact characters"),
                                ("the buffer moved but the history did not", "both inside one lock; test 1: 2000 appends, 2000 steps, 2000 undos to empty"),
                                ("a 4 KB paste swallowed into a typing burst", "the wrapper on the rule; test 8: a paste is always its own step"),
                                ("an edit that threw still got an undo step", "record only after execute succeeded; test 6: no text, version or step changed"),
                                ("a slow or throwing plugin stalls the typist", "fire after the unlock, in a try/catch; test 7: another thread edits mid-notify"),
                                ("the gap left in the wrong place after a caret jump", "moveGap on every edit; test 4: 30 edits match a StringBuilder exactly"),
                                ("the line index drifts from the text after an undo", "it rides on insert/delete; test 9: 150 edits match a full rescan")]):
    y = 16 + k*38
    m9 += _bx(30, y, 400, 34, bad, "") + _ar("M430 %s H470" % (y+17), True) + _bx(470, y, 730, 34, fix, "", acc=True)
m9 += _tx(615, 338, "the three worst ones are silent: a stale redo stack, a history that disagrees with the buffer, and a paste swallowed into a word.", "var(--acc)", 11)
m9 += _tx(615, 357, "nothing throws, the document is simply wrong later -- which is why each of them is a test, not a comment. Nine blocks, and ALL PASS or the page does not build.", "var(--muted)", 11)
MV[9] = _mv(1230, 370, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 840)]
rows10 = [[("Command", "var(--text)"), ("move 2", None), ("interface EditCommand { execute(doc); undo(doc); label(); }", None), ("undo without copying the document", None)],
          [("Memento", "var(--text)"), ("move 2", None), ("DeleteCommand keeps `removed` when it runs", None), ("the smallest state that reverses THIS edit", None)],
          [("Composite", "var(--text)"), ("move 2", None), ("ReplaceAllCommand: children in order, undone in reverse", None), ("forty replacements, one ctrl+Z", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface TextBuffer, interface MergePolicy", None), ("a piece table is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("PasteIsItsOwnStep(rule), RestoresSelection(cmd), LineIndexedBuffer(buf)", None), ("wrap a rule, a command or the storage", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("fire(ev) after the unlock, inside a try/catch", None), ("the view repaints; the typist never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("record() clears redo; undo/redo move between the stacks", None), ("the stale-redo bug cannot happen", None)],
          [("Flyweight", "var(--muted)"), ("not in Main", None), ("Style.of(bold, italic, colour) interns; rich text is a follow-up", "var(--muted)"), ("a million bold characters, one object", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("the Editor is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh Editor per case", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("commands are built at three call sites inside the Editor", "var(--muted)"), ("earns the name when commands come from a journal", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("an insert is an offset and a string; both are required", "var(--muted)"), ("a builder here would be pure ceremony", "var(--muted)")]]
m10 = _D + _table(20, 18, cols10, rows10, rowh=28, widths=1190)
m10 += _tx(615, 375, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 390, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Document knows characters; UndoManager knows stacks and never text; the Editor knows sequencing.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("ReplaceAllCommand and PieceTableBuffer are new files plus one changed line", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 2", None), ("history.undo(doc) pops any command and calls undo blindly &mdash; a composite included", None)],
          [("I", "var(--acc)"), ("small interfaces: one job each", None), ("move 3", None), ("MergePolicy and EditListener have ONE method; the merge rule never learns what a Document is", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("new Editor(buffer, limit, policy); setClock(() -&gt; t); commands take the Document as a parameter", None)]]
m11 = _D + _table(20, 18, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 248, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 262, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a piece table, a different grouping", "a new class behind TextBuffer or MergePolicy, handed in", "", "move 3"),
        ("someone new wants to know", "highlighting, autosave, a plugin", "one more EditListener; the buffer and the lock do not change", "", "move 3"),
        ("a new step in a life", "a macro: begin, record, end", "one more command kind and one composite; record() is untouched", "", "move 6"),
        ("a new invariant across things", "the caret must move with the text", "the caret write inside the SAME lock as the edit: all or nothing", "", "move 4"),
        ("state that must outlive the process", "reopen the file with its undo stack", "a journal of commands written after the unlock, and a replay loop", "commands were already data, so persistence is a codec, not a redesign", "moves 5 + 12")]):
    y = 20 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 308, "and the honest one that is NOT on this list: two people on one buffer. A stack cannot say \"undo mine, keep yours\", because your edit moved my offsets.", "var(--acc)", 11)
m12 += _tx(615, 327, "That is operational transformation or a CRDT, and naming the boundary is worth more in the room than any extra feature.", "var(--muted)", 11)
MV[12] = _mv(1230, 340, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Reading the paragraph again: a <b>user</b> types into a <b>document</b>; the document holds <b>characters</b> and a "
 "<b>caret</b>; each <b>edit</b> can be undone; an <b>undo stack</b> and a <b>redo stack</b> hold them; a "
 "<b>clipboard</b> holds what was cut; <b>views</b> watch. A document has characters and a caret, both of which move: "
 "a class. How those characters are stored is state too, but it is the piece most likely to be swapped, so it becomes "
 "an interface with the document holding one. An edit carries its own state &mdash; where, what, and for a delete, "
 "the characters it removed &mdash; so it is a class, and that is the whole trick: the change is a thing you can "
 "hold. A selection is two ints that never change once made: a record. The grouping rule and a view have no state of "
 "the document at all, so they are interfaces. And notice what is deliberately <i>not</i> a class: a version of the "
 "document. Keeping one per keystroke is the mistake this design exists to avoid.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Put characters in at an offset\" touches the characters, so it belongs to the buffer: "
 "<code>buf.insert(at, s)</code>. \"Remember how to take them out again\" touches nothing but the edit itself, so it "
 "belongs to the command: <code>cmd.undo(doc)</code>, and the command is handed the document as a parameter rather "
 "than storing one, which is what later lets a stored command replay against a fresh document. \"Decide whether two "
 "keystrokes are one step\" touches no state at all: <code>policy.merge(prev, next)</code>, a pure rule. \"Type a "
 "character\" touches the buffer, the history, the version and the listeners at once; only the Editor sees all four, "
 "so it is the orchestrator. And notice what is <i>not</i> a new verb: redo. Redo is <code>execute()</code> again, "
 "which is why the contract on every command is two sentences &mdash; undo exactly cancels the last execute, and "
 "execute is repeatable. Get that second sentence and redo needs no code of its own, and no second place for offsets "
 "to drift.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Three things here will change and you know it before you start. How the characters are stored will change: a "
 "StringBuilder is honest to about a megabyte, a gap buffer past that, a piece table past that again &mdash; so "
 "<code>TextBuffer</code> is an interface with six methods and the Editor is handed one. When edits group will "
 "change: typing groups, a paste never does, an audited document groups nothing &mdash; so <code>MergePolicy</code> "
 "is a one-method interface. Who is told will change: a renderer today, autosave and a syntax highlighter and third "
 "party plugins tomorrow &mdash; so <code>EditListener</code> is a one-method interface. This is where the patterns "
 "come from, not the other way round: a swappable rule behind an interface is <b>Strategy</b>; a rule that wraps "
 "another rule and adds to it is <b>Decorator</b>, and here it is the one that matters &mdash; "
 "<code>PasteIsItsOwnStep</code> wraps whatever grouping rule you hand in and refuses to merge anything that is not "
 "plain typing, so a rule written next year cannot swallow a four-kilobyte paste into one ctrl+Z. An editor that "
 "announces \"something changed\" without knowing what a window is, is <b>Observer</b>. I do them; I do not announce "
 "them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "An editor sounds single-threaded until you say the word autosave, and then there are two threads; add a plugin and "
 "a macro runner and there are four. Applying an edit and recording it are two writes to two different structures. A "
 "thread that slips between them leaves the buffer holding five characters and the history describing four, and they "
 "disagree <i>forever</i> &mdash; the next ctrl+Z deletes the wrong characters and the document is quietly ruined. So "
 "the critical section is not \"the buffer write\"; it is mutate the document, record the command, bump the version "
 "and publish the snapshot, as one unit, owned by the Editor. Guarding only the buffer is the half-fix that still "
 "lets a reader see text at version N beside a history describing N minus one. Two more details are deliberate. The "
 "lock is taken <i>exactly once</i> per edit: every public method &mdash; <code>type</code>, <code>append</code>, "
 "<code>cut</code>, <code>paste</code> &mdash; locks, reads the caret, builds the command, applies it and unlocks, "
 "and only then tells the listeners. Nothing re-enters, which is what makes \"the views are told outside the lock\" "
 "true rather than nearly true: get this wrong and a plugin that blocks for a second blocks every other writer for a "
 "second (there is a test for exactly that). And the Document itself has no lock and no synchronized method, because "
 "per-method locking makes each call atomic and leaves the read-then-write pair torn anyway.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Insert at the caret, again and again\" is a gap buffer: one character array with a hole in it, kept where the "
 "caret is, so typing writes into the hole and costs nothing however long the document is; the array copy is paid "
 "once, when the caret jumps and the hole follows it. \"What do I undo next?\" and \"what do I redo next?\" are two "
 "deques, pushed and popped at the head, both O(1). \"What is on screen?\" is a volatile reference to an immutable "
 "String plus an <code>AtomicLong</code> version, so a renderer and an autosave read without touching the lock and "
 "cannot see a half-written document. \"What does the Edit menu say?\" is the top few labels off the undo stack, "
 "which is why <code>label()</code> was in the command contract from the first line. The memory bound is the same "
 "idea from the other end: a step stores the <i>change</i>, never a copy of the document, and the number of steps is "
 "capped &mdash; and once the oldest step is evicted the document can no longer return to its original, so the "
 "\"unsaved\" dot must come from comparing versions and not from an empty stack.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "The history has exactly four states, defined by whether each stack is empty: CLEAN, CAN UNDO, BOTH, and ALL UNDONE. "
 "One edge is where every bug lives: an edit arriving in BOTH or ALL UNDONE must clear the redo stack. Forget it and "
 "a later redo re-applies an edit at an offset that no longer exists; clear it on undo as well, by mistake, and redo "
 "never works at all. Writing the states down forces the other question too: what is the system after an edit that "
 "threw? The answer is an order. Take the lock; run <code>cmd.execute(doc)</code> first, because that is the step "
 "that can fail, and a command validates its offsets before it touches a character; only if the mutation succeeded "
 "does <code>history.record(cmd)</code> run, because an undo step for an edit that never happened would later delete "
 "somebody else's characters; then the version and the snapshot; then the unlock; then the listeners. A composite "
 "goes further and undoes the children that already ran, and puts the caret back, before letting the exception out: "
 "a half-applied macro must never reach the undo stack.", 6),
("Move 7: yes, the lock makes one document's edits happen one at a time. Ask for how long, and what is inside it.",
 "The question you will be asked, and should ask yourself: if every keystroke takes the document's lock, is the "
 "editor now a queue? It is, for about two microseconds on a twenty-kilobyte file. Inside the lock there is an insert "
 "into the gap (about twenty nanoseconds, because no characters move), one push onto a deque, one call to the "
 "grouping rule, one atomic increment &mdash; and then the part that actually costs: copying the whole document into "
 "a fresh snapshot String, about a microsecond and a half, which is ninety-five per cent of the lock. Everything else "
 "is outside: the repaint at five milliseconds, autosave at three, a highlighter at one, a plugin doing who knows "
 "what, all after the unlock and each in a try/catch. Eight threads appending at the same instant &mdash; which is "
 "literally the first failure test &mdash; make the eighth wait about fourteen microseconds. Name the weak spot "
 "before they do: the snapshot copy is 1.5 us on 20 KB, 60 us on a megabyte, and 600 us on ten megabytes, and that is "
 "the rung you climb next.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "A fast typist is eight keystrokes a second, not eight thousand. At two microseconds of lock each, that is sixteen "
 "microseconds of lock in every second: the lock is busy about two thousandths of one per cent of the time, and two "
 "writers in one document collide roughly never. The lock is per document, so twenty open tabs never meet each other "
 "at all. Then the ladder, in the order you would climb it. First, keep the repaint and the persistence outside the "
 "lock, which this code already does. Second, stop copying the whole document on every edit: publish the version and "
 "the changed range and let readers pull <code>textRange</code>, or swap the buffer for a piece table whose snapshot "
 "is a lazy view &mdash; and because <code>TextBuffer</code> is an interface, exactly one class changes. Third, and "
 "this is the one to say out loud: past one author per document it stops being a lock problem. Two humans need "
 "operational transformation or a CRDT, and no amount of locking makes a stack able to say \"undo mine, keep "
 "yours\".", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Sort them by how loud they are. Three of these bugs throw, and you would find them in a minute: an insert past the "
 "end, an undo before the execute, a composite whose second child is illegal. The other five are silent, and they are "
 "the ones worth testing in front of an interviewer &mdash; a stale redo stack that re-applies an edit at an offset "
 "that no longer exists, a buffer and a history that quietly disagree after a race, a four-kilobyte paste swallowed "
 "into a word, a gap left in the wrong place, an index that drifted from the text. Nothing goes wrong when they "
 "happen; the document is simply wrong later, and nobody knows which keystroke did it. So each one gets a few lines in "
 "FailureTests.java that state the claim as a sentence, and the test for the race deliberately checks three numbers "
 "rather than one: two thousand characters with 1997 undo steps is still a broken editor.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Every pattern here came out of a move, which is why each can be defended in one sentence. <b>Command</b> is move 2: "
 "undo needs the last change rather than the last document, so the change became an object. <b>Memento</b> is the "
 "same move's second half: <code>DeleteCommand</code> keeps the string it removed &mdash; the smallest state that "
 "reverses this one edit, not a copy of the file. <b>Composite</b> is move 2 again: replace-all is a command made of "
 "commands, which is why forty replacements are one ctrl+Z and the Editor gained no method. <b>Strategy</b> is move "
 "3, twice: the buffer and the grouping rule. <b>Decorator</b> is move 3's wrapper and it ends up doing three jobs: "
 "<code>PasteIsItsOwnStep</code> adds one invariant to every grouping rule, <code>RestoresSelection</code> adds a "
 "caret restore to any command, and <code>LineIndexedBuffer</code> adds a line index to any storage &mdash; three "
 "features, and not one existing class was opened. <b>Observer</b> is move 3's rule that a "
 "window must never be inside the lock. <b>State</b> is move 6, the four history states and the edge that clears "
 "redo. <b>Flyweight</b> did not earn a place in Main at all &mdash; it arrives with rich text on page 05, where "
 "<code>Style.of(...)</code> interns so a million bold characters share one object. Singleton earned nothing: the "
 "Editor is handed to its callers, so a test builds a fresh one per case. Factory is \"not yet\": commands are built "
 "at three call sites inside the Editor, and it earns the name the day they arrive as lines from a journal. Builder "
 "is \"never\" here: an insert is an offset and a string, and both are required. A pattern without a move behind it "
 "is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is the check; what is worth saying out loud is the evidence behind it, and the two places this design "
 "bends its own rules on purpose. The evidence: replace-all, macros, rich text and a line index were all added without "
 "opening the Document, the UndoManager or the Editor (S and O); a composite is genuinely substitutable because it "
 "keeps both promises &mdash; execute is repeatable, undo is exact &mdash; by replaying its children in reverse (L); "
 "and every fake a test needs is a lambda, because the interfaces that matter have one method each (I and D). Now the "
 "two bends. <code>EditEvent</code> carries the command object itself, which ties a listener to the command types; a "
 "journal needs exactly that, and inventing a second event format to avoid it would be more coupling, not less. And "
 "<code>ReplaceAllCommand</code> extends <code>CompositeCommand</code> instead of holding one, which is inheritance "
 "used for reuse &mdash; honest here because it really is a composite that fills in its own children, and the day it "
 "needs to be anything else it should hold one instead. Saying where you bent a rule, and why, lands better than "
 "reciting the five letters.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (a piece table for a ten-megabyte file, a grouping rule that never merges, \"bold this selection\") is a "
 "new class behind an existing interface. Someone new who wants to know (incremental syntax highlighting, autosave, a "
 "third-party plugin) is one more listener; the buffer, the history and the lock do not change. A new step in a life "
 "(a macro with an explicit begin and end) is one more composite; <code>record</code> is untouched. A new invariant "
 "across things (the caret must move with the text, even when a macro fails half way) is the extra write inside the "
 "<i>same</i> lock, all or nothing. State that must outlive the process (reopen the file with its undo stack intact) "
 "is a journal of commands written after the unlock and a replay loop &mdash; and it is small precisely because "
 "commands were already data, so persistence is a codec rather than a redesign. Then say the sixth thing, which is "
 "not on the list: two people on one buffer. A stack cannot express \"undo mine, keep yours\", because your edit "
 "moved my offsets. That is operational transformation or a CRDT, and naming the boundary beats any feature you could "
 "add instead. Page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, BookMyShow) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On this problem move 2 is the load-bearing one: the moment a change becomes an "
 "object that carries its own inverse, undo, redo, macros, replace-all and persistence all stop being separate features.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the injected clock, the listeners, the value types the editor hands out
put("clock", 10, 40, 240, "Clock", [], ["nowMs(): long"], "interface")
put("listener", 10, 112, 240, "EditListener", [], ["onEdit(event)"], "interface")
put("renderer", 10, 184, 240, "ConsoleRenderer", [], ["onEdit(e) &rarr; repaint"])
put("autosave", 10, 256, 240, "Autosave", ["latest / savedVersion: long"],
    ["onEdit(e): note the snapshot", "save(): write it, no lock", "isDirty(): versions differ"])
put("event", 10, 380, 240, "EditEvent",
    ["version: long", "kind: edit | undo | redo", "label: String", "text: String (the snapshot)",
     "caret: int", "command: EditCommand"], [])
put("clip", 10, 528, 240, "Clipboard", ["content: String"], ["put(s) / get(): String", "isEmpty(): boolean"])
put("sel", 10, 636, 240, "Selection", ["anchor: int", "caret: int"],
    ["start() / end() / length()", "isEmpty(): boolean", "at(i): Selection"])
# centre column: the aggregate root and what it owns
put("editor", 300, 40, 340, "Editor",
    ["doc: Document", "history: UndoManager", "clip: Clipboard", "lock: ReentrantLock", "version: AtomicLong",
     "snapshot: volatile String", "listeners: CopyOnWriteArrayList"],
    ["configure(policy, views...)", "addListener(l) / setClock(c)", "type(s) / insertAt(at, s) / append(s)",
     "deleteRange(at, len) / backspace()", "cut() / copy() / paste()", "replaceAll(find, repl): int",
     "apply(cmd): long  -- the critical step", "undo() / redo(): boolean", "text() / textRange(a, b) / version()",
     "canUndo() / undoLabels(n)"])
put("doc", 300, 380, 340, "Document", ["buf: TextBuffer", "sel: Selection"],
    ["insert(at, s) / delete(at, len)", "text() / length() / substring(a, b)", "indexOf(needle, from)",
     "select(anchor, caret) / moveTo(c)", "selection(): Selection"])
put("undo", 300, 560, 340, "UndoManager",
    ["undoStack: Deque&lt;EditCommand&gt;", "redoStack: Deque&lt;EditCommand&gt;", "limit: int,  evicted: boolean",
     "policy: MergePolicy"],
    ["record(cmd)  -- clears redo, merges", "undo(doc) / redo(doc)", "canUndo() / canRedo()",
     "depth() / redoDepth()", "labels(n): List&lt;String&gt;", "setPolicy(p)"])
# third column: the rules and the storage, all handed in
put("policy", 690, 40, 250, "MergePolicy", [], ["merge(prev, next): fused or null"], "interface")
put("burst", 690, 116, 250, "TypingBurstMergePolicy", ["windowMs: long", "maxRun: int"], ["one char, forward, same word"])
put("nomerge", 690, 216, 250, "NoMergePolicy", [], ["every keystroke its own step"])
put("paste", 690, 282, 250, "PasteIsItsOwnStep", ["base: MergePolicy (wrapped)"], ["only TYPING may ever merge"])
put("buffer", 690, 372, 250, "TextBuffer", [],
    ["length() / text()", "insert(at, s)", "delete(at, len): String", "substring(from, to)", "indexOf(needle, from)"], "interface")
put("gap", 690, 506, 250, "GapBuffer", ["a: char[]", "gapStart: int", "gapEnd: int"],
    ["insert at the gap: O(1)", "delete: widen the hole", "moveGap(at): one memmove"])
put("sb", 690, 660, 250, "StringBuilderBuffer", ["buf: StringBuilder"], ["honest to about a megabyte"])
# fourth column: the commands
put("kind", 960, 40, 253, "EditKind", ["TYPING, PASTE, DELETE,", "REPLACE, MACRO"], [], "enum")
put("cmd", 960, 128, 253, "EditCommand", [], ["execute(doc)", "undo(doc)", "label(): String", "kind(): EditKind"], "interface")
put("ins", 960, 252, 253, "InsertCommand", ["at: int", "text: String", "kind: EditKind", "atMs: long"],
    ["undo = delete what it put in", "fusedWith(next): a NEW command"])
put("del", 960, 412, 253, "DeleteCommand", ["at: int", "len: int", "kind: EditKind", "removed: String (memento)"],
    ["execute: stash what it removes", "undo = put those characters back"])
put("comp", 960, 572, 253, "CompositeCommand", ["label / kind", "parts: List&lt;EditCommand&gt;"],
    ["execute: in order, all or none", "undo: in reverse"])
put("repl", 960, 700, 253, "ReplaceAllCommand", ["find / replacement: String", "parts: built on first execute", "hits: int"],
    ["40 hits, ONE ctrl+Z"])

def stub(x1, x2, y):
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y, x2, y)

EDGES = [
 # the listeners
 ln(B["renderer"]["t"], B["listener"]["b"], "inherit"),
 ln(B["autosave"]["r"], B["listener"]["r"], "inherit", "", [(256, 309), (256, 139)]),
 ln((300, 60), (130, 112), "notify", "", [(284, 60), (284, 104), (130, 104)]),
 ln(B["autosave"]["b"], B["event"]["t"], "assoc", "receives"),
 # the clock is handed in
 ln(B["clock"]["r"], (300, 86), "inject", "", [(262, 67), (262, 86)]),
 # the editor owns the document, the history and the clipboard
 ln(B["editor"]["b"], B["doc"]["t"], "compose", "owns"),
 ln((300, 240), (300, 661), "compose", "", [(292, 240), (292, 661)]),
 ln((300, 160), (250, 573), "compose", "", [(268, 160), (268, 573)]),
 ln((300, 490), (250, 697), "compose", "", [(280, 490), (280, 697)]),
 # the rules and the storage, handed in
 ln((640, 67), (690, 67), "inject", ""),
 ln((640, 400), (690, 431), "inject", "", [(672, 400), (672, 431)]),
 _tx(815, 30, "the rules and the storage, handed in", "var(--acc)", 10.5),
 ln(B["burst"]["t"], B["policy"]["b"], "inherit"),
 ln(B["nomerge"]["l"], B["policy"]["l"], "inherit", "", [(666, 243), (666, 62)]),
 ln(B["paste"]["l"], B["policy"]["l"], "inherit", "", [(678, 319), (678, 72)]),
 ln(B["gap"]["t"], B["buffer"]["b"], "inherit"),
 ln(B["sb"]["l"], (690, 431), "inherit", "", [(678, 697), (678, 431)]),
 # the history holds commands it did not create
 ln((640, 752), (960, 179), "assoc", "", [(950, 752), (950, 179)]),
 _tx(800, 745, "holds the commands", "var(--muted)", 10.5),
 ln(B["cmd"]["t"], B["kind"]["b"], "assoc"),
 # the four commands implement the interface, on one bus down the right edge
 ln(B["repl"]["r"], B["cmd"]["r"], "inherit", "", [(1226, 753), (1226, 179)]),
 stub(1213, 1226, 321), stub(1213, 1226, 481), stub(1213, 1226, 625),
 _tx(470, 795, "the Editor never builds a rule or a buffer: both arrive through the constructor and configure(), which is why a test can hand it a broken one", "var(--muted)", 11),
]
UMLSVG = uml_svg(1230, 860, EDGES, legend_y=838)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the Editor owns the Document, the UndoManager and the Clipboard, and they die with '
 'it. Plain arrow = references: the UndoManager holds commands it did not create and does not own. Dashed green = '
 'handed in (the buffer, the grouping rule, the clock). Dotted blue = notifies. <b>Where state lives:</b> the characters '
 'live in one TextBuffer behind the Document and nowhere else; the caret lives beside them in the same Document, which '
 'is why the lock covers both; the undo history is two deques of commands and never a single character of text; each '
 'command carries the smallest state that reverses it &mdash; an insert carries its string, a delete carries the string '
 'it removed; and the Editor holds the only lock, the version counter and the published snapshot. Notice what is '
 '<i>not</i> here: no Version or Snapshot class, because a snapshot is an immutable String and a version is a number; '
 'and no separate Redo type, because redo is <code>execute()</code> on the same command.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (nine blocks of claims proven; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (plain or rich text, and how big the document gets, come '
 'first); then type in the order of Main.java: the EditKind enum and the Clock, the Selection record, the TextBuffer '
 'interface with a StringBuilder implementation (the gap buffer can come second), the Document, the EditCommand '
 'interface with InsertCommand and DeleteCommand, the CompositeCommand, the MergePolicy with one real rule and the '
 'wrapper, the UndoManager with its two stacks and its cap, the EditEvent and EditListener, then the Editor with its '
 'lock and the order inside apply(), then a main that types, undoes, redoes, and runs eight threads through '
 'append().</div></div>')

FU = [
("Add find-and-replace-all. Forty hits, and the user expects ONE ctrl+Z.", "twist", 10,
 "Nothing moves. The history class, the lock, the grouping rule and the listeners are untouched, and the Editor gains "
 "no machinery &mdash; replace-all is a command like any other, it just happens to be made of commands. It scans once, "
 "builds a delete and an insert per hit, and builds them from the LAST hit backwards so that replacing a short word "
 "with a long one never moves an offset it has not used yet. Executing runs the children in order; undoing runs them "
 "in reverse, because each child's offsets were computed against the document as the previous child left it. It stays "
 "re-executable, so redo replays the same forty children rather than searching again, which is what stops the offsets "
 "drifting between the two passes.",
 sect(src, "class CompositeCommand", "// \"type five letters")),
("Two threads touch the document at the same instant. Prove you cannot lose an edit, with a test.", "non-functional", 10,
 "The race lives between applying an edit and recording it. apply() does the whole thing &mdash; mutate the buffer, "
 "record the command, bump the version, publish the snapshot &mdash; inside one lock held by the Editor, so no other "
 "writer can run in that gap. The proof is deliberately not a character count: eight threads each append 250 "
 "characters through one latch, and the test then checks the length is 2000, the history has 2000 steps, the version "
 "is 2000, and 2000 undos wind the document back to empty. Two thousand characters with 1997 undo steps is still a "
 "broken editor, so the invariant being tested is that all three agree.",
 T("        // 1. eight threads", "        // 2. the everyday sequence")),
("One lock for the whole document. Have you just serialised the editor?", "non-functional", 5,
 "No, and the answer is arithmetic: eight keystrokes a second against two microseconds of lock each is sixteen "
 "microseconds of lock in every second, and the lock is per document, so twenty open tabs never meet. The shape below "
 "is the part worth defending. Every edit method takes the lock once, builds its command inside that span, applies it, "
 "unlocks, and only then fires; <code>applyLocked</code> exists precisely so that nothing re-enters and no listener "
 "ever runs with the lock held. That is what keeps a five-millisecond repaint, a three-millisecond autosave and a "
 "plugin doing who knows what out of the two microseconds. If they push further, the ladder is: stop copying the whole "
 "document into a snapshot per edit (publish the version and the changed range, or a piece table whose snapshot is a "
 "lazy view), and past one author per document it stops being a lock problem at all.",
 sect(src, "    long apply(EditCommand cmd)", "    /** Type at the caret")),
("An edit throws half way. What is the state of the system?", "functional", 10,
 "Exactly what it was. The order inside apply() is the answer: the lock is taken, the command executes FIRST, and only "
 "if that succeeded is it recorded. A command validates its offsets before touching a character, so an insert past the "
 "end throws with the buffer untouched, no undo step added, the version unmoved and no event published &mdash; the "
 "caller just retries. A composite goes one step further: if its third child throws, the two that already ran are "
 "undone and the caret is put back before the exception leaves, so a half-applied macro can never reach the undo "
 "stack. The order matters more than it looks: recording a command for an edit that did not happen leaves an undo step "
 "that will later delete characters somebody else typed.",
 T("        // 6. an edit that throws", "        // 7. a listener that throws")),
("Five keystrokes should be one ctrl+Z. A four-kilobyte paste should not. Where does that rule live?", "design", 8,
 "Behind a one-method interface, because there are several right answers: typing groups, a paste never does, an "
 "audited document groups nothing at all. The default rule merges only single characters, typed forward from the last "
 "one, close together in time, inside one word and up to a cap, so one undo step is never a whole paragraph. The "
 "important part is the wrapper: PasteIsItsOwnStep sits around whatever rule you hand in and refuses to merge anything "
 "that is not plain typing, so the invariant holds for rules written next year too &mdash; it is the same Decorator "
 "seam as the rest of the design. Swapping the rule at run time is one call and the stacks are untouched; only future "
 "merges change.",
 sect(src, "interface MergePolicy {", "final class UndoManager") + "\n" +
 T("        // 8. the grouping rule", "        // 9. the line index")),
("The document is a ten-megabyte log file and typing has gone slow.", "twist", 10,
 "The buffer is behind an interface, so this is one new class. A StringBuilder copies everything after the edit on "
 "every keystroke, which is invisible at 20 KB and fatal at 10 MB. A gap buffer fixes typing but still pays one array "
 "copy when the caret jumps. A piece table fixes both: the original text is never touched, everything typed is "
 "appended to one growing buffer, and the document is a list of pieces saying which run of characters comes from "
 "where, so an insert or a delete rewrites two or three list entries and copies nothing. The second half of the answer "
 "is the snapshot: copying the whole document per edit is now the expensive part, so the piece table's snapshot "
 "becomes a lazy view and readers keep the same contract. A rope is the other answer, O(log n) for reads and writes at "
 "the price of a tree to rebalance. Commands still speak (offset, length), so exactly one class changes.",
 X("a piece table", "go to line 4000")),
("Undo it after closing and reopening the file. And now the undo stack has to come back too.", "twist", 10,
 "The commands were already data, so persistence is a codec and a replay loop rather than a redesign. A listener "
 "encodes every landed change to one line &mdash; an insert writes its offset and its text, a delete writes its offset "
 "and its length, a composite writes its child count and then its children &mdash; and an undo or a redo writes a "
 "single letter. Startup replays the log into a fresh Editor, which rebuilds the text AND the undo stack, because "
 "replaying the log is exactly what produced them the first time. The journal is a listener, so it writes after the "
 "unlock and a slow disk never blocks a typist; the honest price is that an edit landing in the microsecond before "
 "the process dies is lost, and moving the append inside the lock buys durability at milliseconds per keystroke.",
 X("persistence", "two people at once")),
("Two people editing the same document at once.", "twist", 5,
 "This is the one to name rather than build, and naming it properly is worth more than any feature. A stack can undo "
 "my last step; it cannot undo my last step while keeping yours, because your edit moved my offsets &mdash; my "
 "\"delete three characters at forty\" now means different characters. Two families fix it. Operational transformation "
 "keeps a per-site log and rebases every incoming operation against the ones it had not seen; for two inserts that "
 "whole idea is a four-line function. A CRDT gives every character a unique, totally ordered id instead of an offset, "
 "so there is nothing to rebase, at the cost of carrying those ids forever. In both, undo stops meaning \"pop\" and "
 "starts meaning \"emit the transformed inverse of my own operation\".",
 X("two people at once", "incremental syntax highlighting")),
("The renderer wants to repaint one line, not the file. And there is a syntax highlighter now.", "non-functional", 5,
 "The version number in the event is what makes this cheap, and it was there from the start. A listener compares the "
 "text it last saw with the text in the event, finds the first and last line that differ, and re-tokenises only those "
 "&mdash; one keystroke in a two-hundred-line file costs one line, not two hundred. It never takes the lock, because "
 "the event already carries an immutable snapshot, and a listener that jumps from version 7 to version 9 knows it "
 "missed one and can do a full pass. The Editor also exposes textRange off the same snapshot, so a viewport draws "
 "without copying the whole document.",
 X("incremental syntax highlighting", "plugins")),
("The window shows 50 lines at a time. Draw lines 4000 to 4050 of a 40,000-line file, and put \"line 312, column 7\" "
 "in the status bar.", "functional", 8,
 "You cannot scan for the four-thousandth newline on every repaint, so somebody has to keep an index of where each "
 "line starts. The index rides on the storage, not on the editor: LineIndexedBuffer wraps any TextBuffer and updates "
 "an int array of line starts inside insert and delete &mdash; which means undo and redo maintain it too, for free, "
 "because they go through the same two methods. Nothing above it changes: the Editor, the commands and the lock never "
 "learn it exists, which is the same Decorator seam as PasteIsItsOwnStep, this time around the storage rather than the "
 "rule. A lookup is a binary search, so offset to line and line to offset are both O(log L), and the view then asks "
 "for <code>textRange(startOfLine(4000), endOfLine(4050))</code> off the published snapshot without taking the lock. "
 "The honest cost: an edit near the top shifts every line start below it, one System.arraycopy &mdash; about ten "
 "microseconds on 40,000 lines, and the reason a million-line file wants the newline counts inside a piece table or a "
 "rope instead, where the shift becomes O(log n).",
 X("go to line 4000", "rich text")),
("A plugin somebody else wrote throws on every keystroke. And another one blocks for a second.", "twist", 5,
 "Typing does not notice either of them, and they are two different fixes. Throwing is handled by the try/catch around "
 "each listener: the broken one is skipped, the ones after it are still called, and the edit had already landed before "
 "anybody was told. Blocking is handled by <i>where</i> the notification happens &mdash; after the unlock, in a method "
 "that never re-enters the lock &mdash; so a listener that sleeps for a second delays only itself. The test proves "
 "that second claim the only honest way: from inside a listener it starts another thread that edits the same document "
 "and waits for it, and that edit must land while the notification is still running. The product answer sits one layer "
 "up: a plugin host fans out to the installed plugins and, after three strikes, unsubscribes the offender by name "
 "instead of swallowing the same exception forever.",
 X("plugins", "Runs every extension") + "\n" + T("        // 7. a listener that throws", "        // 8. the grouping rule")),
("Make \"bold this selection\" work, and make ctrl+Z take the bold off.", "twist", 5,
 "A style change is an edit, so it is a command: it goes through apply(), it lands on the undo stack, and one ctrl+Z "
 "reverses it. Its memento is the run list as it was, which is small because a style is a range and not a per-character "
 "attribute. The interesting part is the Style object itself: it is interned, so a million bold characters share one "
 "instance and the table holds references rather than copies &mdash; Flyweight, arriving because rich text demanded it "
 "and not because it was on a list. The one seam that is not free is EditKind: a genuine STYLE constant would be the "
 "single extra edit, and the block below reports MACRO so the merge wrapper refuses to fold a style change into a word.",
 X("rich text", "a macro")),
("Group an arbitrary run of edits into one step — a macro with a begin and an end. And put the caret back on undo.", "twist", 5,
 "Both are small because the seams already exist. A macro buffers commands instead of applying them and hands the "
 "Editor one composite at the end; replace-all is the same shape with the children found by a search instead of by a "
 "caller, which is why macros needed no new machinery in the Editor, the history or the lock. Restoring the caret is a "
 "decorator around any command: it notes the selection before execute and puts it back after undo, so InsertCommand, "
 "DeleteCommand and every composite stay untouched. That is the second use of the same Decorator seam that "
 "PasteIsItsOwnStep uses on the grouping rule.",
 X("a macro", "undo puts the caret back") + "\n" + X("undo puts the caret back", "persistence")),
("Where does time come from, and how do you test that two keystrokes were in the same burst?", "design", 3,
 "The Editor has a Clock it was handed and stamps every insert with it; nothing else in the file reads the wall clock. "
 "A test hands in a clock that returns a fixed instant, types five characters moving it forty milliseconds each time "
 "and asserts one undo step, then moves it five seconds and asserts a second step appears. Without that seam the "
 "grouping test would either sleep or be flaky, which is the usual reason grouping rules ship untested.",
 "/** Where time comes from. Injected, so a test decides whether two keystrokes were 40 ms or 40 minutes apart. */\n"
 "interface Clock { long nowMs(); }\n\n"
 "// on the Editor: handed in, defaulted, never read from the wall clock inside a method\n"
 "private Clock clock = System::currentTimeMillis;\n"
 "void setClock(Clock c) { clock = Objects.requireNonNull(c); }\n\n"
 "// in a test: pick the instant, then move it\n"
 "long[] now = { 1_000_000L };\n"
 "Editor keys = new Editor(new GapBuffer(), 3, new TypingBurstMergePolicy(600, 40));\n"
 "keys.setClock(() -> now[0]);\n"
 "for (char c : \"hello\".toCharArray()) { keys.type(String.valueOf(c)); now[0] += 40; }   // one undo step\n"
 "now[0] += 5000;                                                                     // a pause\n"
 "keys.type(\"x\");                                                                     // a second step\n"),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "Pages 02 and 03 have the full tables; what an interviewer is really testing here is whether you can defend each name "
 "in one sentence and, harder, say where a pattern does <i>not</i> belong. Three are load-bearing and you should say "
 "them first: Command (a change is an object, so undo needs no copy of the document), Composite (replace-all and "
 "macros are commands made of commands, and the Editor gained no method for either) and Decorator, which is used three "
 "times over on three different things &mdash; the grouping rule, the caret restore and the line index &mdash; and is "
 "the honest answer to \"how do I add X without opening anything\". Then the ones that earned nothing. Singleton: the "
 "Editor is handed to its callers, which is why a test can build a fresh one per case. Factory: commands are built at "
 "three call sites inside the Editor, and it earns the name the day they arrive as lines from a journal instead. "
 "Builder: an insert is an offset and a string, both required, so a builder would be pure ceremony. For SOLID the one "
 "worth saying out loud is D: the buffer, the grouping rule and the clock are all handed in, which is exactly why a "
 "test can supply a clock that says last Tuesday, a rule that never merges, and a listener that throws.",
 "// Command + Memento: the change is an object, and a delete carries the smallest state that reverses it\n"
 "interface EditCommand { void execute(Document doc); void undo(Document doc); String label(); EditKind kind(); }\n"
 "public void execute(Document doc) { removed = doc.delete(at, len); }   // DeleteCommand: the memento is filled here\n\n"
 "// Composite: N edits, one undo step; children in order, undone in reverse\n"
 "public void undo(Document doc) { for (int i = parts.size() - 1; i >= 0; i--) parts.get(i).undo(doc); }\n\n"
 "// Strategy: the storage and the grouping rule, both handed in, never built by the Editor\n"
 "Editor(TextBuffer buffer, int historyLimit, MergePolicy policy) { ... }\n\n"
 "// Decorator, three times: around a rule, around a command, around the storage -- add behaviour, open nothing\n"
 "history.setPolicy(new PasteIsItsOwnStep(policy));       // no rule may ever swallow a paste\n"
 "editor.apply(new RestoresSelection(cmd));               // undo puts the caret back too\n"
 "new Editor(new LineIndexedBuffer(new GapBuffer()), ...) // the buffer now knows where every line starts\n\n"
 "// Observer: the Editor announces; it does not know what a window is\n"
 "private void fire(EditEvent ev) { for (EditListener l : listeners) try { l.onEdit(ev); } catch (RuntimeException ignored) { } }\n\n"
 "// State: four history states, and the one edge where the bugs live\n"
 "void record(EditCommand cmd) { redoStack.clear(); /* ... then try to merge, then push, then evict ... */ }\n\n"
 "// Factory: not yet. It earns the name the day commands arrive as journal lines instead of new InsertCommand(...)\n"
 "EditCommand c = CommandCodec.decode(lines, cursor);\n\n"
 "// Builder: never here. Two required fields is a constructor\n"
 "new InsertCommand(at, text, EditKind.TYPING, clock.nowMs());\n"),
]

build(dict(
    slug="text-editor", title="Text Editor",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 9 blocks of failure tests and a 2000-edit race pass",
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
