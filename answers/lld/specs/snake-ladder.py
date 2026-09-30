# Snake and Ladder LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"snake-ladder/Main.java").read_text()
ext   = (H/"snake-ladder/Extensions.java").read_text()
tests = (H/"snake-ladder/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+200])
    j = next(m for m in marks if m > i and b in ext[m:m+200])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"
def M(a, b=None):
    """slice Main.java from the javadoc immediately above `a` to just before the javadoc above `b`, indentation kept"""
    i = src.index(a)
    k = src.rfind("/**", 0, i)
    if k >= 0:
        e = src.find("*/", k)
        if 0 <= e < i and src[e+2:i].strip() == "": i = src.rfind("\n", 0, k) + 1
    j = src.index(b, i) if b else len(src)
    k2 = src.rfind("/**", i, j)
    if k2 > i and src[k2:j].rstrip().endswith("*/"): j = src.rfind("\n", i, k2) + 1
    return src[i:j].rstrip() + "\n"

def R(needle, n=1):
    """n consecutive lines of Main.java starting at the one line containing `needle`: exact code, dedented"""
    import textwrap
    lines = src.split("\n")
    idx = [k for k, l in enumerate(lines) if needle in l]
    assert len(idx) == 1, needle
    return textwrap.dedent("\n".join(lines[idx[0]:idx[0] + n])) + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("take a turn", 30, [("a phone presses roll", "which game, which player"),
                             ("is it this player's turn?", "checked before the die is touched"),
                             ("roll, land, follow jumps", "until a plain cell"),
                             ("write, then pass the turn", "all of it, or none of it")]),
        ("win",         165, [("the token comes to rest", "on the final cell, exactly"),
                              ("checked after the jumps", "a ladder onto 100 wins too"),
                              ("the game is FINISHED", "the winner is recorded"),
                              ("every later roll refused", "the log stops where it stopped")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(370, 95, 370, 40, "refused: not even a die is rolled", "", dash=True)
pf += _tx(88, 266, "read", "var(--acc)", 13) + _tx(175, 266, "at any moment, without replaying the log: where is every token?  whose turn is it?  who won?  how did we get here?", "var(--text)", 12, "start")
pf += _tx(615, 305, "four phones can press roll in the same millisecond: exactly one turn may happen, the token may never move twice, and a refused roll must change nothing at all", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 320, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("turn 13  Alice rolls a 1", ["from 27 she lands on 28", "a ladder at 28 lifts her to 84",
                                    "84 is a plain cell: she stops", "the queue rotates to Bob"], True),
      ("turn 16  Alice rolls a 5", ["from 84 she lands on 89", "a snake at 89 drags her to 68",
                                    "the first snake of the game", "she keeps her place in the queue"], False),
      ("turn 35  Bob rolls a 4", ["from 60 he lands on 64", "a snake at 64 sends him back to 60",
                                  "four steps forward, four steps back"], False),
      ("turn 46  Alice rolls a 2", ["from 98 she rests exactly on 100", "status FINISHED, winner Alice",
                                    "Bob's next roll is refused"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 60 + k*290
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+125) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+125)
    pe += _card(x, 60, 250, 115, t, lines, acc=acc)
pe += _tx(615, 188, "a real run of Main.java, seeded with 7: Alice sat on 98 for six turns because only a 2 would do", "var(--muted)", 11)
P_EX = _mv(1230, 200, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>A board of N cells (100 by default) with snakes and ladders, read from input and checked once, when it is built.</li>
<li>Two or more players in a fixed rotation, each with one token.</li>
<li>One turn: throw the dice, move, follow any snakes and ladders until the token rests on a plain cell, hand the turn on.</li>
<li>A roll that would pass the last cell is wasted; you must come to rest on it to win.</li>
<li>The game ends the instant a token rests on the last cell, and refuses every roll after that.</li>
<li>Only the player whose turn it is may roll.</li>
<li>Every turn is recorded: who, what they threw, where they went, and what carried them.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Many phones rolling at once: one turn happens, no token moves twice, and no turn is lost.</li>
<li>A refused roll costs nothing &mdash; not a position, not a log row, not even a die.</li>
<li>Every lookup in a turn is one hop, O(1): the jump on a cell, whose turn it is, a token's position.</li>
<li>The dice, the overshoot rule and the extra-turn rule are swappable without editing the game.</li>
<li>One source of truth: the game owns every position, the queue and the status, behind one lock.</li>
<li>The same seed plays the same game, so any game can be replayed exactly.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design Snake and Ladder. A board of a hundred cells with snakes and ladders on it, two or more '
          'players taking turns, dice, and a winner. Make it so I can change the rules on you halfway through. '
          'I want working code, not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Players take turns around a board of numbered cells. '
 'On your turn you throw the dice and move that many cells forward. A few cells are special: land on the foot of '
 'a ladder and you are lifted to its top; land on the head of a snake and you slide back to its tail. If that puts '
 'you on another snake or ladder, you take that one too. You win by coming to rest exactly on the last cell; '
 'a throw that would take you past it is wasted, and you stay where you are. Two things have to be true no matter '
 'what. Only the player whose turn it is may move, and a token may never move twice for one turn: that matters '
 'the moment this is an app and four phones can press <i>roll</i> in the same millisecond. And the game has to be '
 'reproducible: if it was random in a way you cannot replay, you cannot test it and you cannot settle an argument '
 'about what happened.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile and run, '
 'with a <code>main</code> that plays a whole game and prints it. The interviewer is watching for, in this order: '
 'the questions you ask before typing (the win rule and whether jumps chain are the first two); which classes '
 'exist and which one owns the positions and the turn order; one turn end to end; what happens when two phones '
 'roll at the same instant; where the rules that will change &mdash; the dice, the overshoot rule, the extra turn '
 'on a six &mdash; live, so a new one is a new class and not an edit; what happens when something in that turn '
 'goes wrong half way. Then the twists: three sixes in a row, playing on for second place, a crocodile and a mine, '
 'landing on another token, a board read from input, take that move back, a player who quits, timers, online play, '
 'persistence.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Do you have to land exactly on the last cell &mdash; and do you need a six to get on the board at all?</td><td>Exactly; a throw that would overshoot is wasted. No entry throw: everyone starts on cell 0 and moves at once</td><td>Both house rules are the same one-method interface, <code>MoveStrategy</code> (move 3)</td></tr>'
 '<tr><td>If a ladder\'s top is a snake\'s head, does the token take the snake too?</td><td>Yes: follow the jumps to a plain cell (the common machine-coding statement says so); a layout that loops is refused when it is built</td><td>A loop in the turn, and a loop check in the board (moves 5, 6)</td></tr>'
 '<tr><td>How many dice, does a six earn another throw, and what do three sixes in a row do?</td><td>One die and no extra throw, both swappable; if sixes do roll again, three in a row cancel all three</td><td>Dice and ExtraTurnRule as handed-in rules (move 3)</td></tr>'
 '<tr><td>Is this one process auto-playing, or an online game with phones?</td><td>Online: several people may send a roll at once</td><td>One lock per game and an out-of-turn refusal (moves 4, 7)</td></tr>'
 '<tr><td>Does the board layout ever change, and who checks it?</td><td>It is read from input once, checked in build(), then frozen</td><td>A builder that fails fast, so the turn loop never validates a layout (move 6)</td></tr>'
 '<tr><td>Do you need to replay a finished game?</td><td>Yes: a bug report is a seed (the number the random rolls start from) and a roll list</td><td>Randomness injected, never <code>Math.random()</code> (moves 3, 9)</td></tr>'
 '<tr><td>How many tables at once, and does anything outlive the process?</td><td>Many tables, in memory, one process</td><td>The game id decides which server holds a game; no repository (the interface state is saved through) yet (moves 8, 12)</td></tr>'
 '<tr><td>Does the game stop at the first winner, or do they play on for 2nd and 3rd?</td><td>It stops at the first winner</td><td>Whether one winner is enough, or the game keeps a finish order (moves 6, 12)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One game, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> you must rest exactly on the last cell; the jumps chain until the token '
 'rests on a plain cell, and a layout that loops is refused; the board is validated once when it is built, never in '
 'the turn loop; the dice, the overshoot rule and the extra-turn rule are handed in; only the player on turn may roll '
 'and the game owns every position behind one lock. Named as out of scope: crocodiles and mines, landing on another '
 'token, playing on for second place, undo, a player who quits, timers, network play, persistence; each is a '
 'follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "PLAYERS take TURNS on a BOARD of cells; a DIE decides how far; SNAKES and LADDERS move you again; somebody WINS", "var(--text)", 12.5)
for x, w, t, sub, acc in [(24, 186, "Game", "positions, queue, status", 1), (222, 168, "Board", "size + the jump table", 1),
                          (402, 150, "Jump", "two cells, one way", 1), (564, 152, "Turn", "what happened, kept", 1),
                          (728, 162, "Player", "an id and a name only", 0), (902, 148, "position", "a field the GAME owns", 0),
                          (1062, 148, "dice, rules", "no state: interfaces", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state that moves: a value, a field on the game, or an interface", "var(--muted)", 11)
MV[1] = _mv(1230, 205, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D
for k, (verb, cls, meth) in enumerate([("throw a number", "Dice  (owns the randomness)", "dice.roll()"),
                                       ("turn a throw into a landing cell", "MoveStrategy  (owns nothing: pure)", "rule.landingCell(from, roll, size)"),
                                       ("follow a landing's jumps", "Board  (owns the jump table)", "board.jumpAt(cell)"),
                                       ("move a token and pass the turn", "Game  (owns positions, queue, status)", "game.roll(playerId)")]):
    y = 24 + k*56
    m2 += _bx(30, y, 330, 44, verb, "the verb") + _ar("M360 %s H430" % (y+22), True)
    m2 += _bx(430, y, 400, 44, cls, "the class whose state it touches", acc=True) + _ar("M830 %s H900" % (y+22), True)
    m2 += _bx(900, y, 300, 44, meth, "the method")
m2 += _tx(615, 269, "a verb whose state is spread over several classes goes to the class that owns them all: the orchestrator, which calls the rest in order", "var(--muted)", 11)
m2 += _tx(615, 288, "and \"win\" is not a verb of its own: it is a comparison the game makes on the cell the token came to rest on", "var(--muted)", 11)
MV[2] = _mv(1230, 300, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _bx(30, 78, 220, 90, "Game", "built by GameBuilder", acc=True)
for k, (t, sub, impl, isub) in enumerate([("Dice", "one die, two dice, scripted", "StandardDice / ScriptedDice / CombinedDice", "the classes that can be handed in"),
                                          ("MoveStrategy", "how far a throw carries you", "OvershootStays / BounceBack / ReachOrPass", "MustRollSixToEnter wraps any of them"),
                                          ("ExtraTurnRule", "a six again? three cancel?", "NoExtraTurn / ExtraTurnOnMax / CappedExtraTurn", "CappedExtraTurn wraps any of them"),
                                          ("GameObserver", "who is told a turn happened", "Commentary / Highlights / analytics / a lambda", "the classes that can be handed in")]):
    y = 24 + k*60
    m3 += _ar("M250 123 H330 V%s H400" % (y+22), True, True) + _bx(400, y, 290, 44, t, sub, dash=True)
    m3 += _bx(750, y, 440, 44, impl, isub) + _ar("M750 %s H690" % (y+22))
m3 += _tx(615, 285, "dashed green = handed in. The game never builds a rule, so a new way to play is a new class and one line in the builder", "var(--muted)", 11)
m3 += _tx(615, 304, "and a rule can wrap a rule: CappedExtraTurn(rule, 3) adds \"three in a row cancel all three\" to any extra-turn rule ever written", "var(--acc)", 11)
MV[3] = _mv(1230, 318, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(30, 30, 200, 44, "Bob's phone", "sees: it is Bob's turn") + _bx(30, 110, 200, 44, "Bob's tablet", "sees: it is Bob's turn")
m4 += _bx(360, 70, 200, 44, "Bob's token", "on cell 34", acc=True)
m4 += _ar("M230 52 H360 V70") + _ar("M230 132 H360 V114") + _tx(295, 40, "roll", "var(--muted)", 10.5) + _tx(295, 160, "roll", "var(--muted)", 10.5)
m4 += '<rect x="590" y="20" width="325" height="140" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(752, 45, "the gap", RED, 12) + _tx(752, 70, "both read \"Bob is due\", both move him:", RED, 11) + _tx(752, 90, "one turn, two moves -- or a skipped player", RED, 11)
m4 += _tx(752, 130, "fix: check, move and rotate as ONE step", "var(--text)", 11)
m4 += _bx(930, 40, 270, 100, "Game.lock", "check + roll + move + rotate", acc=True)
m4 += _tx(1065, 165, "the lock lives where the shared state lives", "var(--muted)", 10.5)
m4 += _tx(1065, 185, "one lock per GAME: a million tables never meet", "var(--muted)", 10.5)
MV[4] = _mv(1230, 200, m4)

# move 5: each collection, its question, its O(1) shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is on the cell I landed on?", "Map&lt;Integer, Jump&gt;  -- sparse: 20 entries on 100 cells", "O(1)"),
                                      ("whose turn is it, and who is next?", "ArrayDeque&lt;playerId&gt;:  peek, poll, addLast", "O(1)"),
                                      ("where is this token?", "Map&lt;playerId, cell&gt;", "O(1)"),
                                      ("how many snakes and ladders were taken?", "EnumMap&lt;JumpKind, Integer&gt;", "O(1)"),
                                      ("how did we get here?", "List&lt;Turn&gt;, append only", "O(1) append")]):
    y = 20 + k*50
    m5 += _bx(30, y, 380, 40, q, "the question") + _ar("M410 %s H460" % (y+20), True)
    m5 += _bx(460, y, 540, 40, shape, "the shape", acc=True) + _ar("M1000 %s H1050" % (y+20), True) + _bx(1050, y, 150, 40, cost, "")
m5 += _tx(615, 290, "no array of a hundred Cell objects: the interesting cells are a handful, so a map stores only what exists and answers in one hop", "var(--muted)", 11)
MV[5] = _mv(1230, 305, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(30, 30, 190, 44, "WAITING", "built and valid, nobody rolls")
m6 += _bx(30, 110, 190, 44, "IN_PROGRESS", "rolls are accepted", acc=True) + _bx(30, 190, 190, 44, "FINISHED", "every roll refused")
m6 += _ar("M125 74 V110", True) + _ar("M125 154 V190", True)
m6 += _tx(145, 96, "start()", "var(--muted)", 10, "start") + _tx(145, 176, "rests on the last cell", "var(--muted)", 10, "start")
m6 += '<rect x="290" y="20" width="920" height="220" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(750, 44, "the order inside one turn, and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1 the game must be IN_PROGRESS and it must be this player's turn -- before the die is touched",
                       "2 read the clock; roll; ask the extra-turn rule; ask the move rule for the landing cell; check it",
                       "3 follow the jumps from that cell until a plain cell; check each end is on the board",
                       "4 decide the win on the RESTING cell, a mine, a capture, and whether this player rolls again",
                       "5 only now write: the positions, the counters, the log row, the places",
                       "6 rotate the queue LAST, so nobody can read a moved token that is still due to roll",
                       "anything that throws in steps 2-4 leaves the game exactly as it was and the same player still to move;",
                       "a roll out of turn is refused in step 1, so it costs nothing at all -- not even a random number"]):
    m6 += _tx(305, 68 + k*22, l, "var(--muted)" if k > 5 else "var(--text)", 11, "start")
m6 += _tx(615, 262, "three states and one rule: nothing is written until the whole turn has been worked out and checked", "var(--muted)", 11)
MV[6] = _mv(1230, 275, m6)

# move 7: what is inside the lock, and four phones at the same instant
m7 = _D + _card(30, 20, 560, 150, "inside the lock: about half a microsecond",
                ["peek the queue, compare one string", "one map get, one arithmetic rule, a map get per jump",
                 "one map put, one deque rotate, one list append", "the die itself: an arithmetic step on a seed",
                 "about ten operations, none of which can block"], acc=True)
m7 += _ar("M590 95 H660", True) + _tx(625, 85, "unlock", "var(--acc)", 10.5)
m7 += _card(660, 20, 540, 150, "outside the lock: milliseconds to seconds",
            ["the commentary and the screens: after the unlock, in a try/catch", "the push to four phones: about 30 ms",
             "the database write: about 5 ms (a follow-up)", "the person deciding to press roll: seconds"])
m7 += _tx(615, 200, "four phones press roll in the same millisecond", "var(--text)", 12)
for k, (t, sub, acc) in enumerate([("p0's phone", "it is p0's turn: 0.5 us", 1), ("p1's phone", "refused after 2 compares", 0),
                                   ("p2's phone", "refused after 2 compares", 0), ("p3's phone", "refused after 2 compares", 0)]):
    m7 += _bx(30 + k*300, 215, 280, 44, t, sub, acc=bool(acc))
m7 += _tx(615, 288, "only one of them is going to do any work, and the other three find that out inside the lock in about a tenth of a microsecond:", "var(--muted)", 11)
m7 += _tx(615, 306, "\"is everything now one by one?\" -- yes, per table, for half a microsecond, and no human being can tell", "var(--muted)", 11)
MV[7] = _mv(1230, 320, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="185" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per game: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["the locked part of a turn: ~10 operations, about 0.5 us",
                       "a real table: 4 people, a roll every 3 seconds = 0.33 rolls/s",
                       "that is 0.17 microseconds of lock in every second: 0.00002% busy",
                       "a million live tables at 300,000 rolls a second across them all",
                       "= 0.15 core-seconds a second, spread over a million SEPARATE locks"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(890, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1 screens and persistence outside the lock", "already done: the phones hear after the unlock"),
                              ("2 one game, one server", "the game id picks the server: each lock stays in one process"),
                              ("3 the game becomes a row in a database", "UPDATE ... WHERE turn_no = ?  -- only if nobody moved first")]):
    m8 += _bx(600, 58 + k*50, 600, 42, t, sub, acc=(k == 0))
MV[8] = _mv(1230, 220, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("two phones roll for the same player at once", "one lock, the turn checked inside it; tests 1-2: 8 threads, exactly one move, one log row"),
                                ("a phone rolls out of turn and costs a die", "every check before the die; test 1: rolls taken out of the dice == turns played"),
                                ("a ladder ends on a snake; jumps loop", "follow the chain; build() refuses a loop; test 3: rests on the first plain cell"),
                                ("a throw that would pass the last cell", "the rule wastes it; test 4: the token stays and nobody wins"),
                                ("a rule or the clock fails half way", "all of it runs before the first write; tests 8, 11: nothing moved, same player due"),
                                ("a bad board layout (two jumps on a cell)", "refused in build(), then frozen; test 7: no Game is ever created"),
                                ("the screen throws while being told", "publish after the unlock, in a try/catch; test 9: the turn still landed"),
                                ("a misclick on the winning roll", "undo walks the writes backwards; test 10: the win is unmade, a is due again")]):
    y = 18 + k*40
    m9 += _bx(30, y, 340, 36, bad, "") + _ar("M370 %s H420" % (y+18), True) + _bx(420, y, 780, 36, fix, "", acc=True)
m9 += _tx(615, 352, "every claim this design makes has a failure test: FailureTests.java runs 88 of them in thirteen blocks and must print ALL PASS", "var(--muted)", 11)
MV[9] = _mv(1230, 365, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 210), ("the line in the code", 300), ("what it buys", 830)]
rows10 = [[("Strategy", "var(--text)"), ("move 3", None), ("interface Dice / MoveStrategy / ExtraTurnRule -- one method each", None), ("a new rule is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("CappedExtraTurn(rule, 3) and MustRollSixToEnter(rule): a rule wrapping a rule", None), ("a cap or an entry gate added to any rule", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(t) after the unlock, inside a try/catch", None), ("screens hear; the table never waits", None)],
          [("State", "var(--text)"), ("move 6", None), ("WAITING &rarr; IN_PROGRESS &rarr; FINISHED, checked first in roll()", None), ("a roll after the win cannot happen", None)],
          [("Command", "var(--text)"), ("move 6", None), ("the Turn record keeps from as well as to; undoLastTurn() walks it backwards", None), ("undo, replay and audit, no extra state", None)],
          [("Builder", "var(--acc)"), ("move 6", None), ("GameBuilder.build(); Game's constructor is package-private", None), ("an invalid game cannot be constructed at all", None)],
          [("Factory", "var(--muted)"), ("not yet", None), ("the builder's dice(count, faces) already picks the class", "var(--muted)"), ("it earns the name when rules arrive as config strings", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("GameServer is handed to its callers; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh server per game", "var(--muted)")]]
m10 = _D + _table(20, 20, cols10, rows10, rowh=30, widths=1190)
m10 += _tx(615, 305, "name a pattern only after the move that produced it; then every name has a one-sentence defence", "var(--muted)", 11)
MV[10] = _mv(1230, 320, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 50), ("from", 450), ("the line that shows it", 560)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Board resolves a landing. Dice makes a number. Game drives the turn. Nobody does two.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("move 3", None), ("ReachOrPass is a new file and one builder line; the turn loop is untouched", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 3", None), ("dice.roll();  never \"is this the scripted one?\" -- which is what makes tests exact", None)],
          [("I", "var(--acc)"), ("small interfaces: one method each", None), ("move 3", None), ("Dice, MoveStrategy, ExtraTurnRule, GameObserver, Clock: one method each", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 6", None), ("new GameBuilder().dice(new ScriptedDice(6, 6, 2)).clock(() -&gt; now)", None)]]
m11 = _D + _table(20, 20, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 250, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 265, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "bounce back, two dice, three sixes cancel", "a new class behind the interface plus one builder line", "", "move 3"),
        ("someone new wants to know", "a scoreboard, analytics, a tournament", "one more observer; the game and the lock do not change", "", "move 4"),
        ("a new step in a life", "a mine, take a move back, a player quits", "one more checked transition, written under the SAME lock", "", "move 6"),
        ("a new invariant across players", "capture: land on a token, it goes home", "the check and the writes inside the SAME lock: all or nothing", "", "move 4"),
        ("state that must outlive the process", "persist it; two servers", "positions and log behind a repository; the turn becomes", "UPDATE ... SET turn_no = turn_no + 1 WHERE turn_no = ?, request id as the key", "moves 5 + 12")]):
    y = 24 + k*54
    m12 += _bx(30, y, 330, 44, t, sub) + _ar("M360 %s H420" % (y+22), True) + _bx(420, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 312, "the first two leave Game untouched; the next two are a few lines inside it, under the same lock; no existing test changes", "var(--muted)", 11)
MV[12] = _mv(1230, 325, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "The game holds every token's position, the turn order and the status, and all of them change every turn: a "
 "class, and the only thing here that owns anything that moves. The board holds its size and its jumps and never "
 "changes once it is built: a class. A snake and a ladder are the same object, a one-way jump from one cell to "
 "another. The only difference is whether the end is below the start, and a sign is not a reason for two classes. "
 "So there is one <code>Jump</code> with a <code>kind()</code> that works it out, and no Snake or Ladder class is "
 "ever written (a crocodile that sends you five cells back is the same object again). A player has an id and a "
 "name and nothing that moves, so it is a record (Java's short, unchangeable data class). The position lives on the "
 "game, and that one decision is what makes the concurrency answer easy later. A turn is worth keeping, so it "
 "is a record too. The dice and the rules own nothing at all, so they are interfaces.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "The picture is the whole move; what matters is the last row. \"Move a token and pass the turn\" touches the "
 "positions, the queue, the status and the log at once. Only the game can see all four, so "
 "<code>game.roll(playerId)</code> is the orchestrator (the one method that calls the others in order), and "
 "everything it calls (the throw, the landing rule, the jump lookup) stays small and stateless. That is also the "
 "answer to a question many candidates get wrong here: the position does not live on <code>Player</code>. Put it "
 "there and two phones can write the same field with no lock in sight. Keep it on the game and the concurrency "
 "answer in move 4 is one sentence, and the same player can sit at two tables at once. And notice what is not a "
 "verb of its own: winning. Winning is a comparison the game makes on the cell the token came to rest on, which is "
 "why it is one line and not a class.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Three things will change, and you can name them before they are asked. How you throw: one die today, two dice "
 "added up (or the highest of three) tomorrow, a scripted die in every test. How far a throw carries you: stay put "
 "on an overshoot today, bounce back tomorrow. The house rule where a token sits off the board until you throw a "
 "six is the <i>same</i> interface, because it too only answers \"which cell does this throw put me on?\". Whether "
 "a six earns another throw: no today; yes tomorrow, with three sixes in a row cancelling all three. Each is a "
 "one-method interface the game is <i>given</i> by its builder and never constructs. This is where the patterns "
 "come from, not the other way round. A swappable rule behind an interface is <b>Strategy</b>. A rule that wraps "
 "another rule is <b>Decorator</b>: <code>CappedExtraTurn</code> adds \"three in a row cancel all three\" to any "
 "extra-turn rule, and <code>MustRollSixToEnter</code> adds the entry gate to any move rule. A game that announces "
 "\"a turn happened\" without knowing what a screen is, is <b>Observer</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "The single-process version of this game needs no lock at all, and saying so is worth a mark: one loop changes "
 "everything, so adding <code>synchronized</code> would protect nothing. The moment it is an app, that changes. "
 "Bob has the game open on his phone and his tablet and presses roll on both. Both read \"it is Bob's turn\", both "
 "roll, both move his token: one turn, two moves, or worse, the queue rotates twice and somebody is skipped. So "
 "checking whose turn it is, throwing, moving and rotating must be <i>one</i> step, in the class that owns all of "
 "it: the game. The lock is per <i>game</i>, not per server, and that is the whole trick. A million tables play in "
 "parallel and never wait for each other; the four people at one table wait in line for half a microsecond. "
 "Anything that only listens (the commentary, the screens) is called after the lock is released, never inside it. "
 "The price: two turns can reach a screen in the wrong order, so each <code>Turn</code> carries its number and a "
 "screen shows them in number order.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers in O(1).",
 "\"What is on the cell I landed on?\" is a map from cell to jump. That is the shape worth defending. A "
 "hundred-cell board has about twenty interesting cells, so an array of a hundred <code>Cell</code> objects stores "
 "eighty empty ones to answer a question a map answers in one hop. If the jump lands on another jump, that is one "
 "more hop, and <code>build()</code> refused every loop, so the chain always ends. (The honest counter-argument: if "
 "a UI arrives and every cell needs a picture and a colour, a dense array becomes the better home. Say that and "
 "move on.) \"Whose turn is it?\" is a deque (a double-ended queue: add or remove at either end), not a list with "
 "an index somebody has to keep. <code>peek</code> to see, <code>poll</code> then <code>addLast</code> to rotate, "
 "all O(1). Two things are not O(1): taking a player out of the middle when they quit, and, when captures are on "
 "(landing on a token sends it back to its start), finding the token on that cell. Both walk the players, fewer "
 "than ten, so it does not matter, and saying that is "
 "better than pretending it is a hash map.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "The three states are in the picture. The six numbered steps beside them are the part to defend out loud, and two "
 "rules produce that order. <i>Check before you spend</i>: the state and the turn are checked before the die is "
 "touched, so a phone that rolls out of turn costs the game nothing, not a log row and not even a random number. "
 "That is what keeps a seeded game (one whose random numbers start from a fixed seed, so it replays exactly) "
 "reproducible, however many stray requests arrive. <i>Compute, then write</i>: the time stamp, the throw, the "
 "landing cell, the jumps and the win all go into local variables and are checked before the first "
 "<code>put</code>. So anything that throws half way, even the clock, which is handed in and can fail too, leaves "
 "the game exactly as it was, with the same player still due. The queue rotates last, or a reader could catch a "
 "token that has moved while its owner is still shown as due. Undo is that same list read upwards, which works only "
 "because every write went through one method in one order. And the board is validated once in "
 "<code>build()</code> and then frozen, so the turn loop never checks a layout it was handed.", 6),
("Move 7: yes, the lock makes one table's turns happen one at a time. Ask for how long, and what is inside it.",
 "Inside the lock: a queue peek and one string comparison, the throw itself (arithmetic on a seed), a map get for "
 "the position, and the move rule (three numbers in, one out). Then a map get for each jump (usually none or one), "
 "one map put, one deque rotation and one list append. That is about ten operations, roughly half a microsecond, "
 "and not one of them can block. Everything slow is outside. The commentary and the push to four phones over "
 "their live connections (tens of milliseconds) happen after the unlock, inside a try/catch, so a screen that has "
 "crashed cannot stop the game. When four phones press roll in the same millisecond, only one of them does any "
 "work. The other three find out they are not on turn after two comparisons, in about a tenth of a microsecond, "
 "and go away. So the answer to \"is everything now one by one?\" is: per table, for half a microsecond, and no "
 "human being can tell.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Four people at a table throw a die every three seconds or so: a third of a roll per second against a lock held "
 "for half a microsecond. The lock is busy about 0.00002% of the time, one second in every ten weeks. Scale it the "
 "other way and it is still fine, because the lock is per game. A million live tables doing three hundred thousand "
 "rolls a second between them is 0.15 of one CPU core of locked work, spread over a million locks that never meet. "
 "Then the ladder, cheapest first. Screens and persistence stay outside the lock, which this code already does. "
 "When one machine is not enough, send every request for a game to the one server that holds it: the game id "
 "picks the server, so each game's lock still lives in one process. Only if any server must be able to serve any "
 "game does the game become a database row, and the turn a conditional UPDATE (it changes the row only if "
 "<code>turn_no</code> still has the value you read). Say the arithmetic first: climbing this ladder without it is "
 "complexity nobody asked for.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "Every row in that table is a claim the design makes, and a claim with no test is an opinion. You will not have "
 "time for all eight in an hour, so write them in this order. The race first, because it is the only one that can "
 "be wrong in a way reading cannot catch. Eight threads wait on a latch (a <code>CountDownLatch</code>: a gate that "
 "lets every waiting thread go at once). Then assert three things: the log has one row per accepted roll, the turn "
 "numbers run 1..n with no gap, and every token starts each turn where its own previous turn left it. Then the one "
 "that proves the <i>order</i> inside the turn: hand in a move rule that returns a cell off the board, or a clock "
 "that throws, and assert the position, the log and the turn order are untouched. Then the two rules everybody "
 "argues about, the overshoot and the chain. The rest (the bad layout, the broken screen, the undo) are three lines "
 "each once those three exist. Say the test out loud while you type it: \"this asserts a refused roll does not "
 "even spend a die.\"", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "Read the table as a defence, one sentence each. Strategy, because move 3 found three rules that change. "
 "Decorator, because two of those rules are better wrapped than copied. Observer, because move 4 said a screen "
 "must never be inside the lock. State, because move 6 gave the game a life, which is why a roll after the win is "
 "refused rather than quietly appended. Command (an action stored as data, so it can be replayed or undone) is the "
 "one candidates miss. The <code>Turn</code> record keeps <code>from</code> as well as <code>to</code>, so the log "
 "is an audit trail, a replay script and the undo stack at once, and <code>undoLastTurn()</code> needs no state of "
 "its own. Builder is the one worth arguing. On most LLDs it is extra code with no job, and you should say so. "
 "Here there are a dozen optional knobs and four invariants (rules that must always hold: two or more players, "
 "unique ids, a legal layout, no loop). <code>build()</code> is the single place they are checked, and Game's "
 "constructor is package-private, so an invalid game cannot be constructed at all. Factory has not earned its name "
 "yet, and Singleton never does. A pattern without a move behind it is decoration.", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "SOLID is not a speech; it is the check that the moves did their job, and every letter here points at a line you "
 "already wrote. The one to say out loud is L, because on this problem it is what makes the tests exist. The game "
 "calls <code>dice.roll()</code> and never asks which dice it got, so a test can hand it a script of 6, 6, 2 and "
 "assert an exact board. If any letter has no line behind it, the honest answer is \"not here\": a letter you "
 "cannot point at is a letter you did not earn.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "A new rule (bounce back, reach-or-pass, two dice or the highest of three, a six to get on the board, three sixes "
 "cancel) is a new class behind an interface that already exists, plus one line in the builder. Someone new who "
 "wants to know (a scoreboard, analytics, a tournament table) is one more observer. A new step in a life is a "
 "checked transition written under the same lock: a mine that holds you for two turns, taking a move back, a "
 "player who quits, playing on for second place. The mine is the one special cell that is <i>not</i> free, because "
 "it changes whose turn it is rather than where a token is; a crocodile is free, because it is a snake of length "
 "five. A new invariant across players (PhonePe's rule: land on a token and it goes back to its start) is the check "
 "and the writes inside the <i>same</i> lock. State that must outlive the process is a repository behind the "
 "positions and the log. The first two kinds leave <code>Game</code> untouched; the next two are a few lines inside "
 "it, under the same lock. None of them changes an existing test, and that is the test that the derivation was "
 "right.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, the "
 "patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is named "
 "before the move that produced it. On this problem two moves do most of the work. Move 1: noticing that a snake and a "
 "ladder are one object deletes a whole class hierarchy before it is born. Move 6: the order inside a turn is the whole "
 "difference between a toy and something you would put four phones in front of.")

# ============================================================ page 03: the class diagram
uml_reset()
# left column: the callers, the listeners, the value types
put("server", 10, 20, 245, "GameServer", ["games: Map&lt;gameId, Game&gt;"],
    ["host(game) / game(gameId)", "roll(gameId, playerId): Turn"])
put("obs", 10, 130, 245, "GameObserver", [], ["onTurn(gameId, turn)"], "interface")
put("comm", 10, 204, 245, "Commentary | Highlights", [], ["onTurn(...) &rarr; a screen"])
put("clock", 10, 278, 245, "Clock", [], ["nowMs(): long"], "interface")
put("player", 10, 352, 245, "Player", ["id: String", "name: String"], [])
put("oot", 10, 448, 245, "OutOfTurnException", ["extends IllegalStateException"], [])
# centre column: the aggregate root, what it owns, and the only way to build it
put("game", 300, 20, 345, "Game",
    ["id: String", "board / dice / moveRule / extraRule / clock", "playToLast / capture: boolean",
     "positions: Map&lt;playerId, cell&gt;", "turns: ArrayDeque&lt;playerId&gt;", "log: List&lt;Turn&gt;,  jumpsTaken: EnumMap",
     "finishOrder: List&lt;playerId&gt;", "sittingOut: Map&lt;playerId, turns&gt;", "status / turnNo / extrasInARow",
     "lock: ReentrantLock"],
    ["start()", "roll(playerId): Turn   &lt;- the critical step", "forfeitTurn(playerId) / undoLastTurn()", "leave(playerId) / playOut(maxTurns)",
     "positionOf(id) / whoseTurn() / status()", "winner() / finishOrder() / history()", "addObserver(o)"])
put("board", 300, 356, 345, "Board",
    ["size: int", "jumps: Map&lt;cell, Jump&gt;", "mines: Map&lt;cell, turns&gt;", "frozen: boolean"],
    ["addJump(j)  -- refuses a loop", "addMine(cell, turns)", "jumpAt(cell): Jump | null   O(1)",
     "holdAt(cell): int   O(1)", "freeze() / size() / jumpCount()"])
put("builder", 300, 572, 345, "GameBuilder",
    ["boardSize / dice / seed / moveRule", "extraRule / clock / jumps / mines / players", "playToLast / capture"],
    ["boardSize(n) / dice(count, faces) / seed(s)", "dice(d) / board(b) / clock(c)", "moveRule(m) / extraTurn(r)",
     "jump(a, b) / crocodile(c) / mine(c, n)", "capture() / playToLast() / player(id, name)",
     "build(): Game  -- checks, then freezes"])
# third column: the value types and the enums
put("jump", 685, 20, 235, "Jump", ["start: int", "end: int"], ["kind(): SNAKE | LADDER"])
# an empty last field gives the enum text room under the <<enum>> header
put("kind", 685, 122, 235, "JumpKind", ["SNAKE, LADDER", ""], [], "enum")
put("status", 685, 198, 235, "GameStatus", ["WAITING, IN_PROGRESS, FINISHED", ""], [], "enum")
put("tkind", 685, 274, 235, "TurnKind", ["PLAYED, CANCELLED,", "HELD, TIMED_OUT", ""], [], "enum")
put("turn", 685, 368, 235, "Turn",
    ["number: int,  playerId: String", "kind: TurnKind", "roll / from / landedOn / to: int", "jumps: List&lt;Jump&gt;",
     "sentHome: playerId | null", "extraTurn / won: boolean", "atMs: long"], ["describe(): String"])
put("next", 685, 566, 235, "Next", ["PASS, AGAIN, CANCEL_STREAK", ""], [], "enum")
# fourth column: the rules that are handed in
put("dice", 960, 20, 260, "Dice", [], ["roll(): int"], "interface")
put("std", 960, 94, 260, "StandardDice", ["count / faces: int", "rng: Random (injected)"], ["roll(): sums n dice"])
put("scripted", 960, 204, 260, "ScriptedDice", ["script: int[]", "used: int"], ["roll(): the next in the script"])
put("move", 960, 324, 260, "MoveStrategy", [], ["landingCell(from, roll, size)"], "interface")
put("stays", 960, 398, 260, "OvershootStays", [], ["past the end = stay put"])
put("bounceb", 960, 472, 260, "BounceBack", [], ["past the end = bounce back"])
put("extra", 960, 556, 260, "ExtraTurnRule", [], ["after(roll, extrasSoFar): Next"], "interface")
put("nox", 960, 630, 260, "NoExtraTurn", [], ["always PASS"])
put("onmax", 960, 704, 260, "ExtraTurnOnMax", [], ["a six: AGAIN"])
put("capped", 960, 778, 260, "CappedExtraTurn", ["base: ExtraTurnRule (wrapped)"], ["3 in a row: CANCEL_STREAK"])

EDGES = [
 # implementations, each on its own lane back to its interface
 ln(B["comm"]["t"], B["obs"]["b"], "inherit"),
 ln(B["std"]["t"], B["dice"]["b"], "inherit"),
 ln(B["scripted"]["l"], B["dice"]["l"], "inherit", "", [(948, 249), (948, 47)]),
 ln(B["stays"]["t"], B["move"]["b"], "inherit"),
 ln(B["bounceb"]["l"], B["move"]["l"], "inherit", "", [(948, 499), (948, 351)]),
 ln(B["nox"]["t"], B["extra"]["b"], "inherit"),
 ln(B["onmax"]["l"], B["extra"]["l"], "inherit", "", [(948, 731), (948, 583)]),
 ln(B["capped"]["l"], (960, 589), "inherit", "", [(930, 815), (930, 589)]),
 # the game owns the board and every turn; the board owns its jumps
 ln(B["game"]["b"], B["board"]["t"], "compose", "the layout"),
 ln((645, 153), B["turn"]["l"], "compose", "", [(656, 153), (656, 453)]),
 ln(B["board"]["r"], B["jump"]["l"], "compose", "", [(676, 449), (676, 65)]),
 ln(B["jump"]["b"], B["kind"]["t"], "assoc"),
 ln(B["turn"]["t"], B["tkind"]["b"], "assoc"),
 ln(B["turn"]["r"], B["jump"]["r"], "assoc", "", [(932, 453), (932, 65)]),
 ln((645, 110), B["status"]["l"], "assoc", "", [(650, 110), (650, 231)]),
 # the rules, handed in by the builder, on one bus under the turn
 ln((645, 200), B["dice"]["l"], "inject", "", [(666, 200), (666, 552), (944, 552), (944, 47)]),
 ln((645, 200), B["move"]["l"], "inject", "", [(666, 200), (666, 552), (944, 552), (944, 351)]),
 ln((645, 200), B["extra"]["l"], "inject", "", [(666, 200), (666, 552), (944, 552), (944, 583)]),
 _tx(806, 549, "the rules, handed in by the builder", "var(--acc)", 10.5),
 # the callers, the roster, the clock and the screens
 ln(B["server"]["r"], (300, 40), "assoc", "", [(275, 65), (275, 40)]),
 ln((300, 60), B["obs"]["r"], "notify", "", [(292, 60), (292, 157)]),
 ln((300, 110), B["player"]["r"], "assoc", "", [(286, 110), (286, 385)]),
 ln((300, 160), B["clock"]["r"], "inject", "", [(278, 160), (278, 305)]),
 ln(B["builder"]["l"], (300, 250), "inject", "", [(268, 665), (268, 250)]),
 ln((300, 220), B["oot"]["r"], "assoc", "", [(262, 220), (262, 473)]),
]
UMLSVG = uml_svg(1230, 905, EDGES, legend_y=880)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (dashed border = interface; &laquo;enum&raquo; = a fixed '
 'list of values). Middle: its fields, the state it holds. Bottom: its methods. <b>The arrows.</b> Hollow triangle = '
 'implements. Filled diamond = owns: the game owns the board and every turn, and the board owns its jumps. Plain arrow '
 '= references: a turn points at the jumps that carried it. Dashed green = handed in by the builder, which is the box '
 'that hands the game its rules and its clock. Dotted blue = notifies. <b>Where state lives:</b> everything that '
 'moves is on the <code>Game</code> (every token\'s position, the turn queue, the log, the places, who is sitting '
 'out a mine, the counters, the status). All of it is behind one <code>ReentrantLock</code>, which is the whole '
 'concurrency answer in one sentence. The board is checked by <code>build()</code> and then frozen. A player is an '
 'id and a name; a jump is two cells; a turn is what happened. Notice what is <i>not</i> here. There is no Snake, '
 'Ladder or Crocodile class, because they are one shape with a sign, and no Cell class, because a cell with nothing '
 'on it is just a number. There is no position field on Player either: the moment two phones can roll, shared state '
 'belongs to whoever holds the lock.')

# ============================================================ page 04: the code
CODE_INTRO = ('The green comment above each class and method says what it does; read only those first for the shape, then '
 'the bodies for the mechanics &mdash; and read <code>Game.roll</code> twice, because the order of its lines is the '
 'design. Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s '
 'reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (88 checks in thirteen blocks; '
 '<code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (exact landing, whether jumps chain, and what three sixes '
 'do come first). Then type in the order of Main.java: the enums, Jump and Player, the Clock, the Dice interface with a '
 'standard and a scripted one, the MoveStrategy interface with its two rules, the ExtraTurnRule with its wrapper, the '
 'Turn record, Board with its checks (the loop check included), then Game with its lock and the order inside '
 '<code>roll()</code>, then GameBuilder, then the thin GameServer, then a main that plays a seeded game and runs the '
 'race. Leave mines, capture, playing on for second place, undo and leaving to their follow-ups. If the clock runs '
 'out, the one thing that must exist is <code>roll()</code> under one lock, with every check and every computation '
 'before the first write.</div></div>')

import textwrap
FU = [
("Every roll is a random number. How do you test that, replay a game, and let the interviewer force the dice? And what if they want two or three dice?", "non-functional", 8,
 "The randomness never comes from inside the game. <code>Dice</code> is an interface and the <code>Random</code> is "
 "handed in, so production passes a seeded one (the same seed gives the same rolls) and a test passes "
 "<code>ScriptedDice</code>, which plays a fixed list of throws. That is PhonePe's \"manual override\": the "
 "interviewer types the throws and checks an exact board. The scripted dice also counts what it handed out, which is "
 "how the race test proves a refused request does not even spend a die. A bug report is then two lines, the seed and "
 "the layout, and failure test 9 plays a seeded game twice and asserts the same rolls, board and winner. "
 "Several dice are one more <code>Dice</code>: <code>CombinedDice</code> throws one die n times and moves by the sum "
 "(two dice give 2 to 12), the highest face or the lowest. The game cannot tell, because all it ever calls is "
 "<code>dice.roll()</code>.",
 sect(src, "final class ScriptedDice implements Dice {", "interface MoveStrategy {") + "\n" + X("several dice", "the board from input")),

("Two phones press roll at the same instant. Prove a token cannot move twice, with a test.", "non-functional", 10,
 "The race lives between \"it is Bob's turn\" and \"Bob has moved\". <code>roll()</code> does the whole thing (the "
 "state check, the turn check, the throw, the move and the rotation) inside one lock held by the game, so no second "
 "caller can get into that gap. The proof is two tests. Eight threads wait on a latch (a gate that lets them all go "
 "at once) and all roll for the same, correct player: exactly one is accepted, the token moved exactly once, the "
 "turn passed exactly once. Then four hundred attempts from eight threads roll for random players, and the log has to "
 "hold up. It has one row per accepted roll, turn numbers 1..n with no gap, and every token starting each turn where "
 "its own previous turn left it; replaying it reproduces the live board.",
 T("        // 1. four phones press roll over and over at the same instant.", "        // 3. a ladder lifts")),

("One lock per game. Does that scale, or have you serialised the server?", "non-functional", 5,
 "It scales, and the answer is arithmetic, not an opinion. Serialised means made to go one at a time. Per table that "
 "is true, for about half a microsecond: a queue peek, a string compare, the throw, two map gets, a map put, a "
 "rotation and a list append, none of which can block. A table rolls about once every three seconds, so its lock is "
 "busy about 0.00002% of the time. And the lock is per game: a million tables doing three hundred thousand rolls a "
 "second is 0.15 of one CPU core of locked work, spread over a million separate locks that never meet. When one "
 "machine is not enough, <code>GameRouter</code> sends every request for a game to the one server that holds it, "
 "picked by the game id. Each game's lock still lives in one process, and <code>Game</code> does not change.",
 X("many servers", "online play") + "\n" + sect(src, "final class GameServer {", "public class Main {")),

("A six rolls again, and three sixes in a row cancel all three. Where does each part go?", "twist", 8,
 "The extra-turn rule is an interface, and it is pure. The game hands it the throw and how many extra throws this "
 "player has had in a row; it answers <code>PASS</code>, <code>AGAIN</code> or <code>CANCEL_STREAK</code>. \"A "
 "six rolls again\" is <code>ExtraTurnOnMax</code>. The three-sixes rule is not a copy of it: "
 "<code>CappedExtraTurn</code> wraps any rule and turns the third <code>AGAIN</code> in a row into a cancel, which is "
 "the Decorator. The game's part is a few lines in <code>roll()</code>. On <code>AGAIN</code> it keeps the same "
 "player on turn and counts the streak (the throws they have made in a row). On <code>CANCEL_STREAK</code> it puts "
 "the token back where the streak began "
 "(the <code>from</code> of the streak's first row in the log) and passes the turn. If the house voids only the third "
 "six, the token stays where it is instead. The test throws three sixes and asserts the token is back on 0 and the "
 "next player is due.",
 sect(src, "enum Next {", "record Turn(") + "\n// in Game.roll(), under the lock: the lines that act on the answer\n"
 + R("Next next = extraRule.after(roll, extrasInARow);", 2) + R("if (!played) {", 3)
 + "    // ... the normal move: the landing cell, then the jumps\n}\n"
 + R("boolean again = played && !won && hold == 0 && next == Next.AGAIN;", 1) + R("if (won) finish(playerId);", 3)),

("Must you land exactly on the last cell? And what if you need a six to get on the board at all?", "functional", 5,
 "Both are the same seam, which is why neither costs a line inside <code>Game</code>. <code>OvershootStays</code> is "
 "the classic rule: a throw that would pass the last cell is wasted and the token stays. <code>BounceBack</code> "
 "sends the extra steps back off the end, and <code>ReachOrPass</code> clamps the landing in one line. The entry rule "
 "is not a fourth copy: <code>MustRollSixToEnter</code> <i>wraps</i> whichever rule you already had and answers 0 "
 "while the token is still off the board, so \"a six to start\" and \"bounce back off 100\" compose for free. The win "
 "check never changes either: <code>to == board.size()</code> on the cell the token came to rest on, so a ladder onto "
 "the last cell wins too.",
 sect(src, "interface MoveStrategy {", "enum Next {") + "\n" + X("the two house rules", "several dice")),

("A ladder's top is a snake's head. Does the token take the snake too? And what if the layout makes a loop?", "functional", 6,
 "Ask, and expect \"yes\": the machine-coding statement Flipkart candidates practise (workat.tech's) says a token "
 "that ends on another snake or ladder keeps going. So <code>roll()</code> follows jumps until the token rests on a "
 "plain cell, and the <code>Turn</code> records every jump it took, in order. A layout can then loop (10 up to 30, 30 "
 "down to 20, 20 back to 10) and move a token for ever. So <code>Board.addJump</code> walks the chain the new jump "
 "would land on, and refuses the jump if the walk comes back to its start. That check runs once, in "
 "<code>build()</code>, and the board is frozen after it, so the turn loop never meets a loop; its own guard only "
 "catches a board subclass that misbehaves. If they say \"one jump per move\" (LeetCode 909's rule), the "
 "<code>for</code> in <code>roll()</code> becomes an <code>if</code>.",
 M("void addJump(Jump j) {", "void addMine(int cell, int turns) {") + "\n// in Game.roll(), under the lock\n"
 + R("for (Jump j = board.jumpAt(to); j != null; j = board.jumpAt(to)) {", 6)),

("They want to play on for second and third place, until one player is left.", "functional", 6,
 "It is a bonus in the common machine-coding statement, and it turns \"one winner\" into a finish order. When a "
 "token rests on the last cell, <code>finish()</code> adds the player to <code>finishOrder</code> and takes them out "
 "of the turn queue (they were its head). The game ends at that first finish unless the builder said "
 "<code>playToLast()</code>; then it ends when only one player is still playing, and that player comes last. Nothing "
 "else changes: the others keep rotating, <code>winner()</code> is first place, and undo un-finishes a player by "
 "putting them back at the head of the queue. The test plays three players on a ten-cell board: a finishes first and "
 "play goes on, b finishes second and the game ends, with c last.",
 M("private void finish(String playerId) {", "private int startOf(") + "\n// GameBuilder\n" + R("/** Play on after the first finisher", 2)),

("A rule you were handed gives back a cell that is not on the board. What is the state of the game?", "functional", 8,
 "Exactly what it was. Nothing is written until the whole turn has been worked out. The time stamp, the throw, the "
 "landing cell, the jumps and the win go into local variables, and the landing and every jump's end are checked "
 "against the board before the first <code>put</code>. So a broken move rule throws, the token has not moved, the "
 "log has no row, the queue has not rotated and the same player is still due; the client simply rolls again. The "
 "clock is read in that first half too, because it is handed in and can fail: read after the first write, a failing "
 "clock would leave a moved token with no log row. The tests hand in a rule that returns <code>size + 99</code>, and "
 "a clock that throws, and assert all four. The one thing that is spent is the die itself, which is honest: the "
 "throw already happened.",
 M("Turn roll(String playerId) {", "Turn forfeitTurn(String playerId)")),

("The screen asks \"what is on cell 47?\" and \"whose turn is it?\" a thousand times a second.", "non-functional", 5,
 "Both are already one hop, and no new structure is needed. A landing resolves through "
 "<code>Map&lt;Integer, Jump&gt;</code>, which stores only the twenty-odd cells that do something rather than a "
 "hundred objects of which eighty are empty; a chain of jumps is one hop per jump. Whose turn it is, is "
 "<code>peek</code> on an <code>ArrayDeque</code>; rotating is <code>poll</code> then <code>addLast</code>, both O(1), "
 "which is why the turn order is a queue and not a list with an index somebody has to maintain. A position is a map "
 "get. These reads take the game's lock, so a caller never sees a half-applied turn; that costs tens of nanoseconds. "
 "If a UI later needs a picture per cell, a dense array of cells becomes the better home and nothing else changes.",
 sect(src, "class Board {", "class OutOfTurnException")),

("\"Take that move back\": the phone fired twice and the wrong roll went in.", "twist", 8,
 "Undo is cheap only because of the order in move 6: every write of a turn goes through one method, in one order, "
 "so undo is that list read upwards. Under the same lock it puts the position back to the turn's <code>from</code>, "
 "brings back a token the move sent home and brings the jump counters down. Then it takes a mine's hold off (or owes "
 "a held turn again), drops the log row, un-finishes a player, and rotates the queue backwards if that turn rotated it. The "
 "extra-throw counter is not stored anywhere else either: it is read back off the log. Two things it deliberately "
 "does not do. It does not un-throw the die, because the throw really happened and pretending otherwise would break a "
 "seeded replay. And it does not tell the observers, because <code>onTurn</code> means a turn happened; telling them "
 "would mean a second method on <code>GameObserver</code>, and a two-method interface is a real cost.",
 M("Turn undoLastTurn() {", "void leave(String playerId)")),

("PhonePe's version: a crocodile takes you five back, a mine holds you for two turns, and landing on another token sends it back to its start.", "twist", 10,
 "Say which are free before you type. The crocodile is free: it is a snake whose tail is five cells below its head, "
 "so <code>crocodile(12)</code> is <code>jump(12, 7)</code>, and the chain, the counters and undo already handle it. "
 "The mine is not free, because it changes whose turn it is rather than where a token is. The board keeps mines "
 "beside the jumps (<code>holdAt(cell)</code>, one map get), and the game keeps who is still sitting out. When a held "
 "player is due, <code>roll()</code> writes a HELD turn without touching the die and passes the turn. Capture is a "
 "rule across players, so it runs inside the same lock. After the move, a token still in play on that cell goes back "
 "to its start (PhonePe starts everyone on 1), and the <code>Turn</code> records whose it was, so undo can put it "
 "back. The test plays seven turns on five throws and checks each effect, then undoes them.",
 "// GameBuilder\n" + R("/** A crocodile takes you exactly five cells back", 2) + R("/** A mine: a token that rests here", 2)
 + R("/** Landing on a cell another token is on", 2) + "\n// Board\n"
 + textwrap.dedent(M("void addMine(int cell, int turns) {", "Jump jumpAt(int cell)")) + R("/** How many turns a token resting here must sit out", 2)
 + "\n// Game.roll(), under the lock\n" + R("if (sittingOut.containsKey(playerId)) {", 3) + "    // ... the throw and the move, in the order of move 6\n"
 + R("int hold = played && !won ? board.holdAt(to) : 0;", 2) + "// ...\n"
 + R("if (sentHome != null) positions.put(sentHome, startOf(sentHome));", 2) + "\n"
 + textwrap.dedent(M("private Turn passWithoutMoving(", "private void passTurn()"))
 + textwrap.dedent(M("private int startOf(", "Turn undoLastTurn()"))),

("Build the game from input: Flipkart-style lines of snakes, ladders and players, or PhonePe's config file of counts with a random board that is valid and can be won.", "functional", 8,
 "The lines are counts and pairs: snakes (head, tail), then ladders (start, end), then the players' names. "
 "<code>BoardInput.read</code> feeds every pair into the same "
 "builder, so a bad board is refused by the same checks in <code>build()</code>; it adds only \"a snake must go down, "
 "a ladder must go up\". PhonePe's config holds counts instead (players, a 10 x 10 board, 9 snakes, 8 ladders, 2 "
 "dice), so <code>GameConfig</code> asks <code>RandomBoard</code> for the layout. Its manual override is the "
 "builder's own seams: <code>ScriptedDice</code> for the throws and <code>startAt</code> for each start cell. The "
 "random board reuses the board's checks instead of copying them: propose a random pair, keep it only if "
 "<code>addJump</code> accepts it, repeat until the counts are met. One question the checks cannot answer: can the "
 "game be won at all? If the six cells before the last are all snake heads, nobody finishes. So <code>winnable</code> "
 "runs a breadth-first search (every cell one throw away, then two, and so on) from 0 and reports whether the last "
 "cell is ever reached, in O(cells x faces).",
 X("the board from input", "turn timers")),

("Make it a real online game: many tables, a request that gets retried, and a phone that disconnects.", "twist", 10,
 "Three separate things. Many tables: <code>GameServer</code> is a map from game id to game with no lock of its own, "
 "so two tables never wait for each other. An out-of-turn roll comes back as its own exception type, so the server "
 "can answer 409 (conflict: \"not your turn\") rather than 500 (a server fault). A retried request must be "
 "idempotent (applied once, however many times it arrives). <code>IdempotentRolls</code> claims the request id with "
 "one atomic <code>putIfAbsent</code> (a single step no other thread can cut into), plays the turn outside the map's "
 "lock, and hands every later copy the same <code>Turn</code>; doing the turn inside <code>computeIfAbsent</code> "
 "instead would let one slow screen stall another table's roll. A phone that disappears for good: <code>leave</code> "
 "takes the same lock, pulls the player out of the queue so the turn passes on at once, and ends the game when one "
 "player is left. A crash still loses the request record; only the database version below survives that.",
 X("online play", "persistence") + "\n" + M("void leave(String playerId)", "Player playOut(")),

("Persist it. And now there are two servers.", "twist", 5,
 "The turn log goes behind <code>GameRepository</code>, whose one write is conditional: "
 "<code>applyTurn(gameId, expectedTurnNo, turn)</code> appends only if the stored game is still on the turn the caller "
 "thinks it is on. In SQL that is <code>UPDATE game SET turn_no = turn_no + 1 ... WHERE game_id = ? AND turn_no = ?</code>, "
 "so the turn number is the version. Zero rows updated means somebody else moved first: re-read and try again. That "
 "is the database doing what the <code>ReentrantLock</code> did in one process, across as many servers as you like: "
 "each server works out the turn exactly as <code>roll()</code> does, and the conditional write picks the one that "
 "counts. The turn row carries the request id with a unique index on it, so a network that delivers the same request "
 "twice applies it once. The in-memory version keeps the same rule, so the seam is tested without a database.",
 X("persistence", "Runs every extension")),

("Where does time come from, and how does a player who has not rolled in thirty seconds lose the turn?", "design", 3,
 "The game has a <code>Clock</code> it was handed and stamps every turn with it; nothing else reads the wall clock. A "
 "test hands in a clock that returns a fixed instant and moves it by hand, so thirty seconds pass in no time at all. "
 "The timer itself is not in the game: it is a small object wired in as an observer, so every turn tells it who is on "
 "the clock now. Either a sweeper thread or the next request asks whether that player is late. When they are, it "
 "calls <code>forfeitTurn</code>, which takes the same lock, writes a TIMED_OUT turn and rotates the queue, so a "
 "forfeit is in the log and the replay like everything else. Who is on the clock, and since when, are one value that "
 "is never modified, swapped in one write. Kept as two fields, a sweeper could pair the new player with the old start "
 "time and forfeit a turn that had just begun; a test forces exactly that moment.",
 X("turn timers", "many servers")),

("Which pattern is where, which SOLID letter is where, and where would a Factory earn its place?", "design", 8,
 "None of them was chosen up front; each is what a move produced, and that is how to say it. Strategy is move 3: the "
 "dice, the move rule and the extra-turn rule are the three things that will change. Decorator is the same move twice "
 "over: <code>CappedExtraTurn</code> wraps an extra-turn rule, <code>MustRollSixToEnter</code> wraps a move rule. "
 "Observer is move 4's rule that a screen is never inside the lock. State is move 6, which is why a roll after the "
 "win is refused. Command is move 6 again, because the <code>Turn</code> record keeps <code>from</code> as well as "
 "<code>to</code>, which is what makes <code>undoLastTurn()</code> possible with no extra state. Builder is the one to "
 "argue: on most LLDs it is extra code with no job. Here there are a dozen optional knobs and four invariants, "
 "<code>build()</code> is the one place they are checked, and Game's constructor is package-private, so an invalid "
 "game cannot exist. Factory has not earned its name: <code>dice(count, faces)</code> already picks the class. It "
 "earns the name the day the rules arrive as strings in a config file, as in PhonePe's version, which is set up from "
 "a YAML or JSON file.",
 "// S: one reason to change each\n"
 "Jump   jumpAt(int cell)                       // Board: what is on a cell\n"
 "int    roll()                                 // Dice: a number\n"
 "Turn   roll(String playerId)                  // Game: the turn loop, and the lock\n\n"
 "// O + L: a new rule is a new file; the caller never asks which one it got\n"
 "final class ReachOrPass implements MoveStrategy {\n"
 "    @Override public int landingCell(int from, int roll, int boardSize) { return Math.min(from + roll, boardSize); }\n"
 "}\n"
 "new GameBuilder().moveRule(new ReachOrPass())         // the only line that changes\n\n"
 "// Decorator: a rule wrapping a rule, on both interfaces\n"
 "new CappedExtraTurn(new ExtraTurnOnMax(6), 3)\n"
 "new MustRollSixToEnter(new OvershootStays())\n\n"
 "// I: one method each, so a test double is a lambda\n"
 "interface Dice          { int roll(); }\n"
 "interface MoveStrategy  { int landingCell(int from, int roll, int boardSize); }\n"
 "interface ExtraTurnRule { Next after(int roll, int extrasSoFar); }\n"
 "interface GameObserver  { void onTurn(String gameId, Turn t); }\n"
 "interface Clock         { long nowMs(); }\n\n"
 "// D: everything is handed in, which is what makes the failure tests possible\n"
 "new GameBuilder().dice(new ScriptedDice(6, 6, 2)).clock(() -> now[0])\n"
 "                 .moveRule((from, roll, size) -> size + 99)   // deliberately broken, in a test\n"),
]

build(dict(
    slug="snake-ladder", title="Snake and Ladder",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 88 checks in 13 failure tests and an 8-thread race pass",
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
