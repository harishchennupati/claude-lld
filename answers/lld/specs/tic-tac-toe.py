# Tic-Tac-Toe LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"tic-tac-toe/Main.java").read_text()
ext   = (H/"tic-tac-toe/Extensions.java").read_text()
tests = (H/"tic-tac-toe/FailureTests.java").read_text()

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
rows = [("play",   30, [("a seat taps a square", "a human, or a bot that just chose"),
                        ("four checks, one step", "live / on board / your turn / empty"),
                        ("stamp it, judge the line", "four counter bumps: O(1) at any size"),
                        ("win, draw, or next seat", "then, after the unlock, the watchers")]),
        ("undo",  165, [("somebody takes it back", "a misclick, or an agreed take-back"),
                        ("five things rewind together", "board, counters, turn, winner, log"),
                        ("the rule un-counts its line", "or a phantom win survives the undo"),
                        ("the same seat plays again", "the game is live exactly as before")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(390, 95, 330, 40, "refused, with a typed reason: nothing is written", "", dash=True)
pf += _tx(88, 262, "read", "var(--acc)", 13) + _tx(175, 262, "at any moment, without scanning the board: whose turn is it?  is it over, and who won?  what is on (1,1)?  what happened, in order?", "var(--text)", 12, "start")
pf += _tx(88, 292, "end", "var(--acc)", 13) + _tx(175, 292, "abandon: a disconnect or a move clock that ran out ends it with no winner, for good; a move that lands first beats a late tick", "var(--text)", 12, "start")
pf += _tx(615, 330, "two clients can submit for the same game in the same millisecond: exactly one move may be accepted per turn, and a refused one changes nothing", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 345, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("21:04:00  Ann taps (1,1)", ["live, Ann's turn, (1,1) is free", "stamped; four counters bumped",
                                   "no line yet: Bob's turn now"], False),
      ("21:04:03  two taps, one square", ["Bob's phone and laptop both send (0,1)", "one stamped, one NOT_YOUR_TURN",
                                          "one mark, one row in the history"], True),
      ("21:06:10  Ann completes column 0", ["colCount[0][X] hits 3 = board size", "WON, winner=Ann, turn stops",
                                            "the scoreboard hears, after unlock"], True),
      ("21:06:14  Ann takes it back", ["colCount[0][X] back to 2, square empty", "IN_PROGRESS, winner=null, Ann up",
                                       "the scoreboard drops the point"], False)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 270, 105, t, lines, acc=acc)
P_EX = _mv(1230, 180, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Create a game: a board size, and two or more seats, each with a name, a mark and a way of choosing squares.</li>
<li>Seats move in a fixed rotation. A move is accepted only if the game is live, it is that seat's turn, and the square is on the board and empty.</li>
<li>An accepted move stamps the mark, appends to an ordered history, and decides the outcome: a win, a draw, or the next seat.</li>
<li>Undo: take the last move back, rewinding the board, the win bookkeeping, the turn and the outcome together.</li>
<li>Abandon: end a game with no winner, for a disconnect or a move clock that ran out. An abandoned game stays abandoned.</li>
<li>Read at any time: whose turn, the state, the winner, the move history, the board as text.</li>
<li>Watchers are told about every accepted move, every undo, every state change and every rejection.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Two clients submitting for one game in the same millisecond: exactly one move per turn, and never two marks on one square.</li>
<li>The default win check is O(1) whatever the board size: four increments, not a scan of rows and columns.</li>
<li>A refused move leaves the board, the turn and the history exactly as they were; the caller retries.</li>
<li>The win rule and a seat's brain are swappable without opening Game or Board.</li>
<li>One source of truth: the move list. Undo, replay and audit all read it.</li>
<li>No printing, no sockets, no sleeping inside the model; watchers are told after the lock is released.</li>
<li>In memory, one process (say it; a follow-up persists the move list).</li></ul></div></div>
'''

PROMPT = ('"Design tic-tac-toe. Two players take turns marking squares, and the first to complete a line wins. '
          'Make the board size a parameter, let a seat be a human or a bot, and assume two clients can submit a '
          'move in the same millisecond. I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Two or more seats take turns putting a mark on a square '
 'of an n&nbsp;&times;&nbsp;n grid. A move is legal only if the game is still live, it is that seat\'s turn, and the '
 'square is on the board and empty. Anything else is refused, and refused in a way that tells the caller whether to '
 'try again in a moment or stop altogether. An accepted move stamps the mark and immediately decides what happened: '
 'it completed a line, so that seat won; or it filled the last square without completing a line, so the game is '
 'drawn; or neither, and the turn passes. It must also be possible to take a move back, which is harder than it '
 'sounds, because one move changes five things at once. The invariant is the rule that must hold at every instant: '
 'one move is accepted per turn, and one mark ever lands on a square. It must hold even when the same person '
 'double-clicks from a phone and a laptop in the same millisecond.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, with '
 'a <code>main</code> that plays a game to the end and then proves the race. The interviewer watches, in this order, '
 'for the questions you ask before typing; which class owns which fact &mdash; storage stores, the rule judges, the '
 'referee arbitrates; one move end to end; what happens when two clients submit at the same instant; where the rule '
 'that will change lives, so "four in a row" is a new class and not an edit; and what the board looks like after a '
 'move is refused halfway through. The twists are the last twenty minutes, and page 05 takes them one at a time.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>A full line on an n&nbsp;&times;&nbsp;n board, or k in a row on a bigger one?</td><td>A full line; k in a row is a follow-up</td><td>O(1) counters instead of a scan, and the rule behind an interface (moves 3, 5)</td></tr>'
 '<tr><td>Two seats, or more?</td><td>Two, but the code must not care</td><td>A dense symbol index (seats numbered 0, 1, 2 with no gaps), and counters sized [line][seat] (moves 1, 5)</td></tr>'
 '<tr><td>Human, bot, or both &mdash; and how clever must the bot be?</td><td>Both; random by default, unbeatable on request</td><td>How a seat chooses is a second one-method interface (move 3)</td></tr>'
 '<tr><td>One console, or a server where two clients move in the same millisecond?</td><td>A server</td><td>One lock per game, and what is allowed inside it (moves 4, 7)</td></tr>'
 '<tr><td>Undo, replay and spectators, or one game played straight through?</td><td>All three</td><td>The move list is the source of truth; watchers are told after the unlock (moves 5, 6)</td></tr>'
 '<tr><td>When a move is illegal: throw, or return false?</td><td>Throw, with a machine-readable reason</td><td>The caller can tell "retry" from "choose another" from "stop" (move 6)</td></tr>'
 '<tr><td>Is a draw only a full board, or the moment nobody can still win?</td><td>A full board; early draw is a follow-up</td><td>One comparison on a running count, not a scan (move 5)</td></tr>'
 '<tr><td>One process and in memory, or does a game survive a restart?</td><td>One process</td><td>No repository yet; persistence is a replay of the move list (move 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One evening, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> the classic rule (a full row, column or diagonal) with the board size as '
 'a parameter; O(1) counters, never a scan; a seat is a name, a mark and an injected brain; a refused move is typed and '
 'writes nothing; the move list is the source of truth; one lock per game, in memory, one process. Out of scope, named '
 'aloud: k in a row, Connect-4, an unbeatable bot, a move clock, persistence, early-draw &mdash; each a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with their own state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "a PLAYER puts a SYMBOL on a CELL of a BOARD; a GAME holds the turn, the history and the outcome; a WIN RULE judges the MOVE; a WATCHER is told", "var(--text)", 12.5)
for x, w, t, sub, acc in [(30, 200, "Board", "the grid, and how full it is", 1), (250, 230, "Game", "turn, history, outcome, lock", 1),
                          (500, 170, "Move", "a record; never edited", 0), (690, 175, "Cell / Symbol", "two ints and a mark", 0),
                          (885, 150, "Player", "a seat: fixed", 0), (1055, 155, "Win rule", "a calculation", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = its state changes, so it becomes a class with a lock over it.   dashed = a value that never changes, or a rule with no state: a record or an interface", "var(--muted)", 11)
m1 += _tx(615, 209, "two things change: the grid and the game's bookkeeping (move 5 adds the win counters). That is the shortlist of what one lock must cover.", "var(--acc)", 11)
MV[1] = _mv(1230, 222, m1)

# move 2: verbs -> the class that owns the state they touch -> methods
m2 = _D
for k, (verb, cls, meth) in enumerate([("choose a square", "MoveStrategy  (owns no game state)", "strategy.chooseMove(board, symbol)"),
                                       ("stamp or lift a mark", "Board  (owns the grid and the count)", "board.place(cell, symbol) / lift(cell)"),
                                       ("judge the move that landed", "WinStrategy  (owns its counters)", "rule.isWinning(board, move)"),
                                       ("accept a move, take one back", "Game  (owns all three, and the turn)", "game.play(player, cell) / game.undo()")]):
    y = 20 + k*54
    m2 += _bx(30, y, 300, 44, verb, "the verb") + _ar("M330 %s H390" % (y+22), True)
    m2 += _bx(390, y, 410, 44, cls, "the class whose state it touches", acc=True) + _ar("M800 %s H860" % (y+22), True)
    m2 += _bx(860, y, 340, 44, meth, "the method")
m2 += _tx(615, 254, "a verb whose state is spread over three classes goes to the one that owns all three: that class is the referee, and it is the only one that changes anything", "var(--muted)", 11)
m2 += _tx(615, 273, "notice what does NOT become a class: there is no Turn and no Winner. The turn is the head of a deque and the winner is one field, both on the referee.", "var(--muted)", 11)
MV[2] = _mv(1230, 286, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 70, 220, 90, "Game", "configure(rule, clock)", acc=True)
for k, (t, sub, impl) in enumerate([("WinStrategy", "how you win: it changes first", "FullLineWinStrategy  /  KInARowWinStrategy"),
                                    ("MoveStrategy", "how a seat picks a square", "Scripted (a human UI)  /  RandomBot  /  Minimax"),
                                    ("GameObserver", "who is told, and what they do", "MoveLogger  /  ScoreBoard  /  SpectatorFeed  /  DeadLineWatcher"),
                                    ("Clock", "where now comes from", "System::currentTimeMillis  /  () -&gt; now[0] in a test")]):
    y = 20 + k*56
    m3 += _ar("M250 115 H330 V%s H390" % (y+22), True, True) + _bx(390, y, 290, 44, t, sub, dash=True)
    m3 += _bx(740, y, 460, 44, impl, "the classes that can be handed in") + _ar("M740 %s H680" % (y+22))
m3 += _tx(615, 262, "dashed = handed in. The Game builds none of these, which is why \"on a 5x5, four in a row wins\" is a new file and one argument.", "var(--muted)", 11)
m3 += _tx(615, 281, "and one observer wraps another: AsyncObserver(feed) puts a slow socket on its own thread, and the feed never knows it was wrapped. That is Decorator.", "var(--acc)", 11)
MV[3] = _mv(1230, 294, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 200, 44, "Bob's phone", "sees (0,0) free, Bob's turn") + _bx(30, 110, 200, 44, "Bob's laptop", "sees (0,0) free, Bob's turn")
m4 += _bx(360, 70, 190, 44, "square (0,0)", "empty", acc=True)
m4 += _ar("M230 52 H360 V70") + _ar("M230 132 H360 V114") + _tx(295, 40, "read", "var(--muted)", 10.5) + _tx(295, 168, "read", "var(--muted)", 10.5)
m4 += '<rect x="590" y="20" width="300" height="150" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(740, 46, "the gap", RED, 12) + _tx(740, 70, "both stamp: one mark overwrites", RED, 11) + _tx(740, 90, "the other, two moves land for one", RED, 11)
m4 += _tx(740, 110, "turn, and the history is a lie", RED, 11)
m4 += _tx(740, 145, "fix: check AND write as ONE step", "var(--text)", 11)
m4 += _bx(920, 40, 280, 110, "Game.lock", "check, stamp, judge, rotate = one step", acc=True)
m4 += _tx(1060, 178, "the lock lives where the changing state lives", "var(--muted)", 10.5)
m4 += _tx(1060, 197, "one lock per GAME: ten thousand tables never wait", "var(--muted)", 10.5)
MV[4] = _mv(1230, 212, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("whose turn is it, and who is next?", "ArrayDeque&lt;Player&gt;, rotated", "O(1)"),
                                      ("did the move that just landed win?", "int[line][seat] counters, 4 bumps", "O(1)"),
                                      ("is the board full?", "a running filled count", "O(1)"),
                                      ("what is on that square?", "Symbol[n][n], indexed", "O(1)"),
                                      ("what happened, and in what order?", "ArrayList&lt;Move&gt;, append only", "O(1) append")]):
    y = 20 + k*46
    m5 += _bx(30, y, 380, 38, q, "the question") + _ar("M410 %s H470" % (y+19), True)
    m5 += _bx(470, y, 480, 38, shape, "the shape", acc=True) + _ar("M950 %s H1010" % (y+19), True) + _bx(1010, y, 190, 38, cost, "")
m5 += _tx(615, 268, "nothing here reads a row or a column. The only O(n&sup2;) methods on the board &mdash; freeCells, render, copy &mdash; are for bots and screens, never for the win check.", "var(--muted)", 11)
m5 += _tx(615, 287, "the counters are the whole trick and they have a price: they are state, so undo must decrement them, and they can only answer \"is this WHOLE line mine\".", "var(--acc)", 11)
MV[5] = _mv(1230, 300, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(20, 80, 160, 40, "NOT_STARTED", "created, no moves")
m6 += _bx(210, 80, 160, 40, "IN_PROGRESS", "turn = deque head", acc=True)
m6 += _bx(390, 20, 120, 40, "WON", "winner set") + _bx(390, 80, 120, 40, "DRAW", "board full")
m6 += _bx(380, 140, 140, 40, "ABANDONED", "timeout, disconnect")
m6 += _ar("M180 100 H210", True) + _ar("M370 95 L390 45", True) + _ar("M370 100 H390", True) + _ar("M370 110 L380 155", True)
for yy, xx in [(40, 510), (100, 510)]:
    m6 += '<path d="M%s %s H545" fill="none" stroke="var(--muted)" stroke-width="1.3" stroke-dasharray="5 4"/>' % (xx, yy)
m6 += _ar("M545 100 V8 H290 V80", dash=True)
m6 += _tx(400, 232, "dashed = undo(): it takes back a WON or a DRAW; ABANDONED is final", "var(--muted)", 10.5)
m6 += '<rect x="570" y="20" width="640" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(890, 44, "the order inside play(), and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  take the lock; check terminal, bounds, turn, emptiness -- nothing is written",
                       "2  stamp the mark, then ask the rule. If the rule throws, lift the mark back off",
                       "3  ask \"did it win\" BEFORE \"is the board full\": a line on the last square WINS",
                       "4  append the move, rotate the turn, unlock -- and only then tell the watchers",
                       "a refused move leaves the board, the turn and the history exactly as they were;",
                       "undo is the same list in reverse: pop, un-count, lift, rewind turn and outcome"]):
    m6 += _tx(585, 72 + k*23, l, "var(--muted)" if k > 3 else "var(--text)", 11, "start")
m6 += _tx(615, 256, "five things move together on every accepted move: the grid, the counters, the sequence, the turn and the outcome. Anything that rewinds must rewind all five.", "var(--muted)", 11)
MV[6] = _mv(1230, 270, m6)

# move 7: what is inside the lock, and many callers at the same instant
m7 = _D + _card(30, 20, 560, 128, "inside the lock: under a tenth of a microsecond",
                ["four checks: terminal, bounds, turn, emptiness", "one array write, and filled++",
                 "four counter bumps and four comparisons", "one list append, one deque rotate",
                 "about fifteen field touches, whatever n is"], acc=True)
m7 += _ar("M590 84 H660", True) + _tx(625, 74, "unlock", "var(--acc)", 10.5)
m7 += _card(660, 20, 540, 128, "outside the lock: milliseconds to minutes",
            ["the brain choosing: minimax, a few milliseconds", "the spectator socket: ~50 ms, after the unlock",
             "a person staring at the board: seconds", "rendering and freeCells: O(n&sup2;), for screens",
             "the board snapshot a bot reads: taken, then released"])
m7 += _tx(615, 175, "ten clients hammering the SAME game at the same instant", "var(--text)", 12)
for k in range(10):
    x = 30 + k*118
    m7 += _bx(x, 190, 106, 40, "client %d" % (k+1), "waits %s" % ("0" if k == 0 else "~%d us" % (k*10)), acc=(k == 9))
m7 += _tx(615, 258, "the tenth client waits about 0.1 ms: each hand-off wakes a sleeping thread (~10 us), far longer than the work inside. Nobody can tell.", "var(--muted)", 11)
m7 += _tx(615, 277, "the deliberate part: a bot thinks on a COPY of the board taken under the lock and released. It may lose the race, and a lost race is a normal retry.", "var(--muted)", 11)
MV[7] = _mv(1230, 290, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="210" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per game: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a move: ~15 field touches, under 0.1 us",
                       "two people playing: one move every 5 seconds",
                       "that is 0.1 us of lock in every 5,000,000 us: 0.000002% busy",
                       "10,000 live tables on one server: one lock EACH, they never meet",
                       "50 bots hammering ONE table: the last waits ~0.2 ms (hand-offs)",
                       "the slow thing is the minimax search, and it is outside the lock"]):
    m8 += _tx(35, 68 + k*26, l, RED if k == 5 else "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 nothing slow inside the lock", "already done: brains, sockets and rendering are outside it"),
                              ("2 spectators read without the lock", "state and winner are volatile; history and board come back as copies"),
                              ("3 compare-and-set instead of a lock", "on each square and on a turn token -- and three more things to roll back")]):
    m8 += _bx(600, 60 + k*56, 600, 46, t, sub, acc=(k == 0))
m8 += _tx(615, 250, "rung 3 is the one to say out loud and then decline: it makes the stamp race-free, but the turn, the counters and the outcome still need their own rollback.", "var(--muted)", 11)
MV[8] = _mv(1230, 264, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two clients, one square, one instant", "one lock per game; test 1: 50 threads, exactly one accepted, one mark, one row"),
                                ("the wrong seat, or a taken square", "a typed reason and no write; test 2: board, turn and history identical after three rejections"),
                                ("the win rule throws halfway through", "lift the mark back off; test 3: the move never happened, and the retry lands"),
                                ("undo forgets the counters", "rule.undo() rewinds them; test 4: replay the same square, it wins again"),
                                ("the last square completes a line", "win is judged before full; test 5: WIN, not DRAW"),
                                ("the spectator throws, or blocks", "after the unlock, in a try/catch, on its own thread; test 7: both proven")]):
    y = 18 + k*42
    m9 += _bx(30, y, 330, 38, bad, "") + _ar("M360 %s H410" % (y+19), True) + _bx(410, y, 790, 38, fix, "", acc=True)
m9 += _tx(615, 292, "every claim this design makes has a failure test: FailureTests.java runs nine blocks, thirty-seven checks, and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 305, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 190), ("the line in the code", 280), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface WinStrategy { boolean isWinning(Board, Move); }", None), ("four in a row is a new file, not an edit", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface MoveStrategy { Cell chooseMove(Board, Symbol); }", None), ("human, random and minimax: one code path", None)],
          [("Observer", "var(--text)"), ("move 3", None), ("publishMove(m) after the unlock, each in a try/catch", None), ("the scoreboard hears; the game never waits", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new AsyncObserver(feed, 8192) -- same kind in, same kind out", None), ("a slow socket drops frames, never a move", None)],
          [("State", "var(--text)"), ("move 6", None), ("GameState.isTerminal() guards every entry point", None), ("an illegal move cannot happen", None)],
          [("Command", "var(--text)"), ("move 6", None), ("the Move IS the command: pop it, un-count it, lift it", None), ("undo, redo and replay are one list", None)],
          [("Singleton", "var(--muted)"), ("not here", None), ("GameService is handed to its callers; nobody calls getInstance()", "var(--muted)"), ("a test builds a fresh service", "var(--muted)")],
          [("Factory", "var(--muted)"), ("not yet", None), ("newGame(id, size, seats, rule) already picks the default rule", "var(--muted)"), ("it earns the name when rules arrive as config strings", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a game is an id, a size and its seats: all three required", "var(--muted)"), ("a pattern without a move behind it is decoration", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 335, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 350, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 430), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Board stores. WinStrategy judges. Game referees. An observer reports. Nobody does two.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("KInARowWinStrategy is a new file plus one argument to configure()", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("rule.isWinning(board, m);  a stateless rule keeps the default undo() rather than throwing", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("WinStrategy, MoveStrategy, Clock: one method. GameObserver's four are all defaults.", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("game.configure(new KInARowWinStrategy(4), () -&gt; now[0])", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "k in a row, mis&egrave;re, a bigger board", "a new class behind WinStrategy plus one configure argument", "", "move 3"),
        ("someone new wants to know", "a scoreboard, a socket, an early-draw watcher", "one more observer; the lock and the rule do not change", "", "move 3"),
        ("a new step in a life", "a pause, a rematch offer, a forfeit", "one more state and one more checked transition", "", "move 6"),
        ("a new invariant across squares", "Connect-4: a piece falls to the bottom", "map the column to the lowest free row BEFORE play()", "drop(column) is the only door, so a column only grows: a lost race is CELL_TAKEN", "moves 4 + 6"),
        ("state that must outlive the process", "resume after a restart; two servers", "persist the MOVE LIST, not the board; loading is a replay", "a board can never be restored into a position the rules would not allow", "moves 5 + 12")]):
    y = 24 + k*56
    m12 += _bx(30, y, 330, 46, t, sub) + _ar("M360 %s H420" % (y+23), True) + _bx(420, y, 650, 46, fix, sub2, acc=True) + _tx(1150, y+28, mv, "var(--muted)", 11)
m12 += _tx(615, 322, "for all five, Board, Game, Move and the failure tests do not change. That is the test that the derivation was right.", "var(--muted)", 11)
MV[12] = _mv(1230, 336, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "Underline the nouns in the prompt, then sort them by one question: does anything about this change during a game? "
 "The <b>board</b> changes (the grid, and how full it is) and the <b>game</b> changes (the turn, the history, the "
 "winner), so those two are classes. A <b>move</b> never changes once it has happened, so it is a record (a Java "
 "value class whose fields are fixed when it is made). A <b>cell</b> is two ints and a <b>symbol</b> is a mark plus a "
 "number, so those are records too. A <b>player</b> is a name, a mark and a way of choosing, none of which move "
 "mid-game. A <b>win rule</b> is a calculation, so it is an interface; move 5 gives the default one counters, and the "
 "game's lock covers those too. Two classes with changing state is the shortest possible list for a lock to cover, "
 "and that is the whole point of doing this sort first.",
 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "\"Choose a square\" touches no game state &mdash; it reads a board and returns a cell &mdash; so it belongs to a "
 "rule of its own. \"Stamp a mark\" and \"lift it off\" touch the grid, so they belong to the board. \"Did that move win\" "
 "touches the win counters, so it belongs to the rule that keeps them. \"Accept a move\" touches all three at once, "
 "plus the turn, and only the game sees all four. So the game is the referee, the only class that changes anything, "
 "and <code>game.play(player, cell)</code> is its main door. Notice what does <i>not</i> become a class. No Turn "
 "class: the turn is the head of a deque (a queue you can take from at the front and add to at the back). No Winner "
 "class: the winner is one field. Either one would give you two places that "
 "must agree about the same fact, which is how these implementations end up with a board that says one thing and a "
 "flag that says another.",
 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Four things here will change, and you know which. How you win changes first &mdash; \"on a 5x5, four in a row\" is "
 "the standard follow-up &mdash; so <code>WinStrategy</code> is a one-method interface. How a seat picks a square "
 "changes (a human UI, a test script, a random bot, an unbeatable one), so <code>MoveStrategy</code> is a second. Who "
 "is told changes (a log today, a scoreboard and a websocket later), so <code>GameObserver</code> is a third. And "
 "where \"now\" comes from changes the moment you write a test about a move clock, so <code>Clock</code> is a fourth. "
 "The game is <i>given</i> all four and builds none. The patterns fall out of that, not the other way round: a "
 "swappable rule behind an interface is <b>Strategy</b>; announcing without knowing who is listening is "
 "<b>Observer</b>; wrapping another of the same kind to add one behaviour is <b>Decorator</b>, which here is "
 "<code>AsyncObserver</code>. Do them; do not announce them.",
 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Bob double-clicks, or his phone retries while his laptop is still trying. Two threads both read \"the game is live, "
 "it is Bob's turn, (0,0) is empty\" and both stamp: one mark overwrites the other, two moves land for one turn, and "
 "the history now says something that never happened. Worse, if the two threads are different seats, both can complete "
 "a line and you get two winners. So the four checks and the stamp are not five operations, they are one, and they "
 "live in the class that owns the board and the turn: the game. The lock is per <i>game</i>, not per server, which is "
 "the whole trick: ten thousand tables run at once and never wait for each other. The two people at one table are "
 "serialised (made to go one at a time) for well under a microsecond. Anything that only listens is called after the "
 "lock is released.",
 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"Whose turn is it?\" is the head of an <code>ArrayDeque</code>, rotated rather than an index modulo the seat count, "
 "because rotation gives you \"give the turn back\" free on undo and a third seat free as well. \"Did that move win?\" "
 "is the interesting one. The obvious answer walks the row, the column and both diagonals after the move, which is "
 "O(n) and re-reads squares that cannot have changed. A move only touches four lines, so keep a counter per (line, "
 "seat) instead: four increments and four comparisons, the same work at 3x3 and at 1000x1000. Be honest about the "
 "crossover, because you will be asked. On a 3x3 the scan is twelve reads and the counters save nothing. They are not "
 "a speed win at the size in the prompt; they are what makes \"now do it on a 1000x1000\" a non-event. And they have "
 "a price: they are mutable state, so undo must decrement them, and they can only answer \"is this <i>whole</i> line "
 "mine\" &mdash; which is exactly why the rule sits behind an interface and not inside Board.",
 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "A game is NOT_STARTED, then IN_PROGRESS, then WON, DRAW or ABANDONED &mdash; not \"over: true\". One enum with an "
 "<code>isTerminal()</code> means every entry point asks one question instead of three booleans drifting apart, and "
 "ABANDONED makes a disconnect or an expired move clock a real ending rather than a game that hangs forever. Writing "
 "the states down forces the order at the critical step, and three details in it are what interviewers push on. Every "
 "check runs before anything is written. If the rule throws after the mark is stamped, the mark is lifted back off, "
 "because a half-applied move is worse than a refused one. And \"did it win\" is asked <i>before</i> \"is the board "
 "full\", so a line completed on the last free square is a win and not a draw &mdash; the single ordering most people "
 "get wrong. Undo is the same list read backwards, and it must rewind all five things a move changed. It can take "
 "back a win or a draw but never an abandon, because the last move is not why that game ended.",
 6),
("Move 7: yes, the lock makes one game's moves happen one at a time. Ask for how long, and what is inside it.",
 "If every move takes the game's lock, is the server now a queue? It is &mdash; for under a tenth of a microsecond "
 "per move (35 to 75 nanoseconds, measured on a laptop), and only for the people at that one table. The locked part "
 "is about fifteen field touches, and it does not grow with the board size. When ten clicks collide, the wait is the "
 "hand-off: waking each sleeping thread takes about ten microseconds, so the tenth waits about a tenth of a "
 "millisecond. Everything slow is outside the lock, and the bot is the case worth saying out loud. "
 "<code>playAuto()</code> copies the board into a snapshot (a private copy of one instant) under the lock, releases "
 "it, and only then asks the brain. The copy is O(n&sup2;): nothing on a 3x3, about two milliseconds on a "
 "1000&nbsp;&times;&nbsp;1000, and a human UI skips it by handing a cell in directly. The brain can lose the race "
 "while it was thinking: it gets CELL_TAKEN or NOT_YOUR_TURN and tries again, which is a normal outcome, not an error.",
 7),
("Move 8: say the arithmetic, then name the ladder.",
 "One move every five seconds, against a lock held for under a tenth of a microsecond, keeps the lock busy about two "
 "millionths of one per cent of the time. Ten thousand live tables do not change that number, because each has its "
 "own lock and they never meet. Then the ladder. Rungs one and two this code already climbed: nothing slow inside the "
 "lock, and <code>state</code> and <code>winner</code> are volatile (read fresh by every thread, with no lock). So a "
 "spectator polling the score never queues behind a move. Rung three is the one to say out loud and then decline. It "
 "swaps the lock for compare-and-set (one hardware step that writes only if the value is still what you read) on each "
 "square and on a turn token. It makes the stamp race-free, but the turn, the counters and the outcome then need a "
 "rollback path of their own: more moving parts, for a game whose concurrency is two.",
 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The table is the list; two rows deserve a sentence. Undo clearing the square but forgetting the counters is the "
 "classic bug of this system, and it is invisible to the obvious test: the square <i>is</i> empty afterwards. So the "
 "test is not \"is the square empty\" but \"replay that same square and check it wins again\", which only passes if "
 "the counters came back down too. And the win-before-full ordering is tested by playing a line that completes on the "
 "ninth square of nine: WON, not DRAW. Each row is a few lines in FailureTests.java, which runs nine blocks and "
 "thirty-seven checks; block 9 covers the edges of the follow-ups. A design that cannot show its tests is a claim.",
 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Read the table rather than a list of definitions: each row names the move that produced the pattern, so each name "
 "has a one-sentence defence. Two names need a plain gloss. State here is just the GameState enum that every entry "
 "point checks, and Command is the Move record: an action kept as data, so undo, redo and replay read one list. The "
 "bottom three rows matter as much as the top six. Saying \"Singleton, not here\" and "
 "\"Builder, never here\" out loud is what separates a design from a pattern parade, and \"Factory, not yet\" names "
 "the exact condition that would change the answer: rules arriving as strings from configuration.",
 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "One letter is worth more than the table row gives it. L is the one people fumble: a stateless rule keeps the "
 "interface's default no-op <code>undo()</code> rather than throwing \"unsupported\", because a substitute that "
 "throws is not a substitute &mdash; that is why <code>undo()</code> is a default method and not an abstract one. And "
 "D is not decoration here: it is precisely why a test can hand the game a rule that explodes on demand and a clock "
 "that claims it is thirty-one seconds later.",
 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "The last two rows are the ones worth rehearsing. Connect-4 sounds like a new engine and is not: \"a piece lands on "
 "the lowest free row of its column\" is a mapping applied <i>before</i> <code>play()</code>. Clients get only "
 "<code>drop(column)</code>, never a raw play or an undo, so a column can only grow while they think. The same lock "
 "decides, and a lost race is the ordinary CELL_TAKEN retry. Persistence sounds like serialising a board and is "
 "not: you persist the move <i>list</i>, and loading replays it through <code>play()</code>, so a saved game can "
 "never come back in a position the rules would not allow. Page 05 has the working code for all five.",
 12),
]
DERIVATION_LEAD = ("Run these on any LLD and the class diagram, the lock, the tests, the patterns, SOLID and the answer to "
 "every twist fall out in that order; nothing is chosen up front, and nothing is named before the move that produced it. "
 "Tic-tac-toe looks too small for a derivation, which is exactly the trap: the interview is not about the rules of the "
 "game, it is about which class owns which fact, what happens when two clients move at once, and what an undo has to "
 "rewind.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the caller, the listeners and the clock
put("app", 10, 20, 230, "GameService", ["games: Map&lt;id, Game&gt;", "standing: List&lt;GameObserver&gt;", "clock: Clock"],
    ["newGame(id, size, seats, rule)", "game(id) / live() / end(id)", "addObserver(o) / setClock(c)"])
put("obs", 10, 175, 230, "GameObserver", [], ["onMove / onUndo (game, move)", "onStateChange(game, from, to)", "onRejected(game, p, cell, e)"], "interface")
put("log", 10, 280, 230, "MoveLogger", [], ["narrates a game to stdout"])
put("score", 10, 350, 230, "ScoreBoard", ["decided: Map&lt;gameId, name&gt;"], ["wins(name): int"])
put("async", 10, 442, 230, "AsyncObserver", ["base: GameObserver (wrapped)", "pump: 1 thread, capped queue"], ["delivers off the move's thread"])
put("clock", 10, 548, 230, "Clock", [], ["nowMs(): long"], "interface")
# centre: the aggregate root and what it owns
put("game", 300, 20, 340, "Game",
    ["id: String", "board: Board", "players: List&lt;Player&gt;", "turnOrder: Deque&lt;Player&gt;",
     "history: List&lt;Move&gt;", "lock: ReentrantLock (fair)", "winRule / clock / observers", "state, winner (volatile); turnStartedMs"],
    ["configure(rule, clock)", "play(player, cell) / playAuto(): Move", "undo() / abandon(why) / abandonIfIdle(ms)", "state() / winner() / currentPlayer()",
     "history() / at(cell) / render()", "snapshot(): Board"])
put("board", 300, 320, 340, "Board", ["size: int", "grid: Symbol[size][size]", "filled: int"],
    ["place(cell, symbol) / lift(cell)", "inBounds / isFree / isFull / at", "freeCells() / copy() / render()"])
put("move", 300, 492, 340, "Move", ["player: Player", "cell: Cell", "seq: long,  atMs: long"], ["symbol(): Symbol"])
# third column: the values and the enums
put("state", 700, 20, 230, "GameState", ["NOT_STARTED, IN_PROGRESS", "WON, DRAW, ABANDONED"], ["isTerminal(): boolean"], "enum")
put("exc", 700, 120, 230, "InvalidMoveException", ["reason: Reason"], ["OUT_OF_BOUNDS | CELL_TAKEN", "NOT_YOUR_TURN | GAME_OVER", "NO_FREE_CELL"])
put("player", 700, 240, 230, "Player", ["name: String", "symbol: Symbol", "strategy: MoveStrategy"], ["decide(board): Cell"])
put("symbol", 700, 368, 230, "Symbol", ["mark: char", "index: int (dense slot)"], [])
put("cell", 700, 456, 230, "Cell", ["row: int", "col: int"], [])
# fourth column: the rules that are handed in
put("win", 970, 20, 250, "WinStrategy", [], ["isWinning(board, move): boolean", "undo(board, move)  -- default"], "interface")
put("full", 970, 110, 250, "FullLineWinStrategy", ["rowCount / colCount: int[n][seats]", "diagCount / antiCount: int[seats]"],
    ["four ++ and four ==  : O(1)", "undo: the same four, --"])
put("kin", 970, 240, 250, "KInARowWinStrategy", ["k: int"],
    ["walks out 4 ways: O(k)", "stateless: default undo()", "+ ScanWinStrategy: the O(n) one"], "extension")
put("mvs", 970, 358, 250, "MoveStrategy", [], ["chooseMove(board, symbol): Cell"], "interface")
put("brains", 970, 432, 250, "Scripted | RandomBot", [], ["a human UI, and a seeded bot"])
put("mini", 970, 506, 250, "MinimaxStrategy", ["opponent: Symbol"], ["alpha-beta on a Board.copy()"], "extension")

EDGES = [
 # the observer implementations, on a bus down the right of the left column
 ln(B["log"]["t"], B["obs"]["b"], "inherit"),
 ln((240, 387), (240, 218), "inherit", "", [(254, 387), (254, 218)]),
 ln((240, 485), (240, 218), "inherit", "", [(268, 485), (268, 218)]),
 # the win rules and the brains
 ln(B["full"]["t"], B["win"]["b"], "inherit"),
 ln((970, 285), (970, 55), "inherit", "", [(952, 285), (952, 55)]),
 ln(B["brains"]["t"], B["mvs"]["b"], "inherit"),
 ln((970, 543), (970, 385), "inherit", "", [(952, 543), (952, 385)]),
 # the game owns its board and every move
 ln(B["game"]["b"], B["board"]["t"], "compose", "the grid"),
 ln((300, 200), (300, 530), "compose", "", [(284, 200), (284, 530)]),
 # the rules and the clock are handed in; the watchers are told
 ln(B["game"]["t"], B["win"]["t"], "inject", "", [(470, 6), (1095, 6)]),
 _tx(790, 16, "configure(rule, clock)", "var(--acc)", 10.5),
 ln((300, 250), (240, 575), "inject", "", [(276, 250), (276, 575)]),
 ln((300, 60), (240, 210), "notify", "", [(262, 60), (262, 210)]),
 ln(B["app"]["r"], (300, 90), "assoc", "keeps"),
 # the game points at its enums and its seats; a rejection is typed
 ln((640, 100), (700, 65), "assoc", "", [(700, 100)]),
 ln((640, 130), (700, 173), "assoc", "throws", [(700, 130)]),
 ln((640, 175), (700, 293), "assoc", "seats", [(700, 175)]),
 # the values
 ln((640, 391), (700, 391), "assoc", "holds"),
 ln((640, 520), (700, 490), "assoc", "", [(700, 520)]),
 ln(B["player"]["b"], B["symbol"]["t"], "assoc"),
 ln((930, 293), (970, 385), "assoc", "brain", [(970, 293)]),
]
UMLSVG = uml_svg(1230, 644, EDGES, legend_y=620)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values; &laquo;extension&raquo; = it lives in Extensions.java, not in the core file). Middle: its fields, the '
 'state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = implements. Filled diamond = owns: the game '
 'owns its board and every move ever accepted. Plain arrow = references. Dashed green = handed in through '
 '<code>configure()</code>, which is why the game builds no rule and no clock. Dotted blue = notifies, and it happens '
 'after the lock is released. <b>Where state lives:</b> only Board (the grid, and how full it is) and Game (the turn, '
 'the history, the outcome, and the one lock over all of it) hold state that changes. The lock is fair: waiting '
 'threads get it in arrival order. FullLineWinStrategy is the third '
 'and it is deliberate: its counters are what make the win check O(1), and the price is the <code>undo()</code> in the '
 'interface. Everything else is a value or a rule with no state at all. Notice what is <i>not</i> here: no Turn class, '
 'because the turn is the head of a deque; no Winner class, because the winner is one field; and no win logic inside '
 'Board, because then "four in a row" would reopen the class that holds the grid.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above each '
 'class and method says what it does; read only those first for the shape, then the bodies for the mechanics. Each copy '
 'button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s reference code, with '
 'an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (nine blocks, thirty-seven checks; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (full line or k in a row, and one process or a server, '
 'first). Then type in the order of Main.java: the GameState enum, the Symbol / Cell / Move records, the typed '
 'InvalidMoveException, the Clock, then Board with nothing but storage in it, then the WinStrategy interface with the '
 'counter rule, then MoveStrategy with a scripted seat and a random bot, then Player, then GameObserver with a logger '
 'and a scoreboard, then Game with its lock and the order inside play(), then the thin GameService, then a main that '
 'plays a scripted game and runs fifty threads at one square. The must-write core is the enums and records, Board, '
 'the counter rule, Game with play() and undo() under its lock, and the race in main. The async wrapper, the scoreboard '
 'and GameService are the parts to name and skip if the clock runs short.</div></div>')

FU = [
("On a 5x5, four in a row wins. How much of your code changes?", "twist", 10,
 "One new class and one argument. The counters in FullLineWinStrategy only answer \"is this whole line mine\" and "
 "cannot see four inside a row of five, so this is a different rule rather than a patched one: it walks outward from "
 "the square that was just played in four directions and counts the run. That is O(k) per move instead of O(1), which "
 "is the honest cost and worth saying out loud. It keeps no state, so it inherits the interface's no-op "
 "<code>undo()</code> &mdash; which is why undo sat behind a default rather than being abstract. Board, Game, Player, "
 "Move and every observer are untouched; the only other line that moves is the one that hands the rule in. Databricks "
 "asks it on a rectangle (\"Rectangular K-in-a-Row\"), and this rule still does not change, because it only walks "
 "outward and <code>at()</code> returns null off the board; Board would take rows and columns instead of one size.",
 X("k in a row", "the scan rule")),
("Two clients submit a move for the same game in the same millisecond. Prove you cannot get two marks on one square.", "non-functional", 10,
 "The race lives between reading \"that square is empty, and it is your turn\" and writing the mark. play() does the "
 "whole thing &mdash; the terminal check, the bounds check, the turn check, the emptiness check, the stamp, the win "
 "judgement and the turn rotation &mdash; inside one lock held by that game, so no other writer can run in the gap. "
 "The proof is a count rather than an eyeball: fifty threads wait on one latch and all fifty submit the same square, "
 "half as one seat and half as the other. Exactly one must be accepted, forty-nine must come back with a typed "
 "reason, the board must hold one mark, the history one row, and the turn must have rotated exactly once. Expect the "
 "second half of the question: the network drops your reply and the client sends the same move again. The turn has "
 "already passed, so the copy comes back NOT_YOUR_TURN (or GAME_OVER if that move won) and nothing doubles. The client "
 "then reads the last move in the history to see that it was its own.",
 T("        // 1. fifty threads stamp", "        // 2. every rejection")),
("One lock per game. Have you just serialised your game server?", "non-functional", 5,
 "No, and the answer is arithmetic. The locked part is about fifteen field touches &mdash; four checks, one array "
 "write, four counter bumps, an append and a rotate &mdash; under a tenth of a microsecond, and it does not grow "
 "with the board size. Two people make one move every five seconds, so the lock is busy about two millionths of one "
 "per cent of the time. Ten thousand live tables do not change that, because the lock is per game and they never "
 "meet. What would ruin it is slow work inside the lock, so none is allowed: the code below is the clearest case, a "
 "bot getting a board copy and thinking after the unlock. Spectators are told after the unlock too, and "
 "<code>render()</code> only copies the board under the lock and builds the text after it.",
 sect(src, "Move playAuto()", "Move undo()")),
("Your win rule throws halfway through a move. What is the state of the board?", "functional", 5,
 "Exactly what it was. Every check &mdash; is the game live, is the square on the board, is it your turn, is it empty "
 "&mdash; runs before anything at all is written, so a refused move never reaches the grid. The one operation after "
 "the first write that can fail is the rule itself, and it is wrapped: if <code>isWinning</code> throws, the mark is "
 "lifted straight back off and the exception goes to the caller, so the sequence number, the history and the turn "
 "never moved. The rule's side of the contract is written in its Javadoc: it must be all-or-nothing about its own "
 "counters, because the referee will only undo the board. The failure test hands in a rule that explodes on demand, "
 "checks the square is empty and the game is identical, then lets the retry through.",
 sect(src, "Move play(Player player, Cell cell)", "Move playAuto()")),
("The board is 1000 x 1000. Is your win check still one operation?", "non-functional", 5,
 "Yes: four increments and four comparisons, whatever n is. A move can only touch four lines &mdash; its row, its "
 "column, and the two diagonals if it happens to sit on them &mdash; so instead of scanning anything, keep one counter "
 "per (line, seat) and compare it to the board size. The dense symbol index makes those counters plain int arrays, "
 "not hash lookups on the hot path (the code every move runs), and a third seat costs nothing. "
 "This is LeetCode 348; its two-player answer keeps one counter per line instead, +1 for X and &minus;1 for O, and a "
 "line is won at +n or &minus;n. Two honest costs go with it: the counters are mutable state, so undo has to "
 "decrement them, which is why <code>undo()</code> is in the interface from the start. And they can only answer \"is "
 "this whole line mine\", which is exactly why the rule is swappable.",
 sect(src, "interface WinStrategy", "// \"human, random bot") + "\n" +
 T("        // 6. the four counters", "        Cell[] sameXs")),
("It is a 3x3 board. Are the counters over-engineering, and why not just scan?", "design", 5,
 "On a 3x3 alone you would be right, and saying so is the answer they want. A scan of the four lines through the "
 "square just played is at most twelve array reads, it holds no state, and it needs no <code>undo()</code>: at that "
 "size the counters save nothing and cost you a rewind path. What buys them their place is one sentence in the "
 "prompt, <i>make the board size a parameter</i> &mdash; at 1000 x 1000 the scan is four thousand reads a move and "
 "the counters are still eight operations. So put the rule behind an interface, ship the counters as the default "
 "because the size is open, and keep the scan as the other implementation. The code below is both, and a failure test "
 "plays one scripted game through each and checks they agree on the winner, the move and the board: Liskov with a "
 "result instead of a slogan.",
 X("the scan rule", "gravity") + "\n" +
 T("        Cell[] sameXs", "        // 7. observers run after")),
("Make it Connect-4: pieces fall to the bottom of a column.", "twist", 10,
 "Gravity is a mapping, not a new engine: the rule is already <code>KInARowWinStrategy(4)</code>. The only new idea "
 "is that a piece dropped into column c lands on the lowest free row of c, computed before <code>play()</code>. "
 "Because <code>play()</code> knows nothing about gravity, clients get only <code>drop(column)</code>, never a raw "
 "play or an undo, and the column bot below uses the same mapping. Then a column can only grow while a player thinks, "
 "and the same lock still decides. If someone fills that square first, the move comes back CELL_TAKEN and the caller "
 "drops again, the ordinary retry that typed rejections bought in move 6. One honest gap: a real Connect-4 board is 7 "
 "wide and 6 tall, and Board here is square, so Board would need a row count and a column count.",
 X("gravity", "the unbeatable bot")),
("Write me a bot that never loses on a 3x3.", "twist", 10,
 "Minimax with alpha-beta pruning, and it is a new MoveStrategy and nothing else &mdash; the engine does not know bots "
 "exist. It plays every legal move on a copy of the board, assumes the opponent answers with their best, and picks the "
 "move whose worst outcome is highest; depth is folded into the score so a win in three beats the same win in five, "
 "and alpha-beta drops branches that cannot change the answer. It judges those hypothetical positions with its own "
 "full scan, which is fine: they are not the hot path, and the real game still uses the O(1) counters. "
 "<code>Board.copy()</code> exists for exactly this, and the failure test plays the bot against a random one over five "
 "seeds and asserts it never loses.",
 X("the unbeatable bot", "undo and redo")),
("Undo. Then undo the undo.", "functional", 5,
 "Undo is the interesting method in this system, because a move changed five things and all five have to come back: "
 "the mark on the grid, the rule's counters, the sequence number, the turn and the outcome. Forgetting the counters is "
 "the classic bug &mdash; the square looks empty while the rule still believes somebody has three in a row &mdash; so "
 "the test is not \"is the square empty\" but \"replay the same square and check it wins again\". The turn comes back "
 "by rotating the deque until the seat that made the undone move is at the head. Watchers hear "
 "<code>onUndo</code>, so a spectator's board loses the mark too, and an abandoned game refuses undo, because its "
 "last move is not why it ended. Redo needs nothing from the engine: the undone moves go on a stack and are replayed "
 "through the ordinary <code>play()</code>, so they pass every check again and a new move simply clears the stack.",
 sect(src, "Move undo()", "void abandon") + "\n" + X("undo and redo", "persistence")),
("The process restarted mid-game. Bring the game back.", "twist", 5,
 "Persist the move <i>list</i>, not the board. Loading is creating a fresh game with the same seats and the same rule "
 "and replaying those moves through <code>play()</code>, which rebuilds the grid, the counters, the turn and the "
 "outcome as a side effect. Each row names its seat by symbol index, not by name, because two seats may share a name. "
 "Every restored move goes through the same four checks, so a saved game can never come back in a position the rules "
 "would not allow. The same list is the audit trail. In a database this is a moves table keyed by (game id, "
 "sequence), where undo deletes the last row and a retried insert fails harmlessly on the key.",
 X("persistence", "a move clock")),
("Each seat gets thirty seconds a move. Where does time come from, and how do you test it?", "twist", 5,
 "Time comes from a one-method <code>Clock</code> handed to the game; nothing in the model reads the wall clock, and "
 "every move is stamped with it. The game notes when each turn began: when the last move landed, or when an undo gave "
 "the turn back. One scheduled task sweeps every live game once a second and calls <code>abandonIfIdle(30 s)</code>, "
 "which reads the time and abandons in one step inside that game's lock. So a move that lands a microsecond before "
 "the tick always wins, and a tick after a win does nothing. The test owns the clock. A move lands at 29 seconds with "
 "its watchers held back, a tick at 31 finds the game still live, and a seat idle past 30 seconds is timed out.",
 sect(src, "boolean abandonIfIdle", "// Listeners run after") + "\n" + X("a move clock", "three seats")),
("A spectator is on a slow websocket. Prove it cannot slow the game down, or break it.", "non-functional", 5,
 "Three separate things, and each is a line of code. Watchers are told after the lock is released, so a spectator "
 "never runs inside the locked part at all. Each callback runs in its own try/catch, so a spectator that throws cannot "
 "break the move &mdash; the mark is already stamped and the game has already decided. And a spectator that is merely "
 "slow gets wrapped: <code>AsyncObserver</code> takes any observer and delivers to it on one background thread from a "
 "fixed-size queue. When the queue is full it drops the oldest event, so a client that cannot keep up loses frames "
 "rather than slowing the game. That wrapper is the Decorator on this page: same kind in, same kind out, and the feed "
 "inside never knows. The test blocks a wrapped spectator on a latch, checks the move returned in about zero milliseconds "
 "with the spectator still stuck, then releases it and checks it was told anyway.",
 sect(src, "class AsyncObserver", "class Game {") + "\n" +
 T("        // 7. observers run after", "        // 8. the twists really")),
("Three players on a 5x5. And can you tell it is a draw before the board fills?", "twist", 8,
 "Three players cost nothing, which is the payoff of the dense symbol index: the counters are already sized "
 "[line][seat], the turn is a rotation and not an index modulo two, and the only guard to revisit is that the seats "
 "must not outnumber the board's width. Early draw is the more interesting half. A line is dead once two different "
 "marks appear in it, and when every row, column and diagonal is dead nobody can win. It is written as an observer "
 "precisely so the engine does not move: it scans a snapshot after each move, O(n&sup2;). Say the limit before you "
 "promise it &mdash; the earliest a 3x3 can be dead is after the eighth of nine squares, so it buys one move there "
 "and only pays on bigger boards. Making it free means a \"distinct marks\" count per line inside a rule, and that is "
 "the one twist on this page that reopens Game.",
 X("three seats", "early draw") + "\n" + X("early draw", "a game server")),
("Which pattern is where, which SOLID letter is where, and where would a Factory or a Builder earn its place?", "design", 8,
 "Answer it as six lines of code, not six definitions &mdash; the snippet below is the whole answer, and moves 10 and "
 "11 are the same thing as two tables. Strategy twice (the win rule, the seat's brain), Observer plus the rule that it "
 "runs after the unlock in a try/catch, Decorator as AsyncObserver, State as the GameState enum, Command as the move "
 "list that doubles as the undo log. SOLID lands on the same lines: S is move 2's split, O and D are "
 "<code>configure()</code> taking a rule it never built, L is the default no-op <code>undo()</code> that a stateless "
 "rule can keep, I is three interfaces of one method each. The two worth saying unprompted are the refusals: Factory "
 "earns its place the day rules arrive as configuration strings, and Builder never earns one here, because a game is "
 "an id, a size and its seats and all three are required.",
 "// Strategy, twice: the two things that change, each behind one method, each handed in\n"
 "interface WinStrategy  { boolean isWinning(Board board, Move move); default void undo(Board b, Move m) { } }\n"
 "interface MoveStrategy { Cell chooseMove(Board board, Symbol symbol); }\n"
 "void configure(WinStrategy rule, Clock clock) { this.winRule = rule; this.clock = clock; }\n\n"
 "// Observer: the game announces, after the unlock, and a broken listener cannot break a move\n"
 "private void publishMove(Move m) { for (GameObserver o : observers) try { o.onMove(this, m); } catch (RuntimeException ignored) { } }\n\n"
 "// Decorator: same kind in, same kind out, one behaviour added\n"
 "GameObserver socket = new AsyncObserver(new SpectatorFeed(), 8192);\n\n"
 "// State + Command: the life is a fixed set of moves, and the move list IS the undo log\n"
 "enum GameState { NOT_STARTED, IN_PROGRESS, WON, DRAW, ABANDONED }\n"
 "Move gone = history.remove(history.size() - 1);   winRule.undo(board, gone);   board.lift(gone.cell());\n\n"
 "// Factory: not yet. newGame already picks the default; it earns the name when rules come from config strings\n"
 "Map<String, WinStrategy> byName = Map.of(\"FULL_LINE\", new FullLineWinStrategy(n, seats), \"K4\", new KInARowWinStrategy(4));\n\n"
 "// Builder: never, here. Three required fields is a constructor\n"
 "new Game(id, size, seats);\n"),
]

build(dict(
    slug="tic-tac-toe", title="Tic-Tac-Toe",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 9 test blocks and a 50-thread race pass",
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
