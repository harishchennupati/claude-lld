# Chess LLD workbench: problem -> twelve moves -> the class diagram -> the whole code -> follow-ups and practice.
import sys, re
sys.path.insert(0, "/Users/harishchennupati/answers/lld")
from lld_engine import *

src   = (H/"chess/Main.java").read_text()
ext   = (H/"chess/Extensions.java").read_text()
tests = (H/"chess/FailureTests.java").read_text()

def X(a, b):
    """slice Extensions.java between two '// ---- ext:' markers (b may name the ExtDemo block)"""
    marks = [m.start() for m in re.finditer(r"(?m)^// ---- ext:", ext)] + [ext.index("/** Runs every extension")]
    i = next(m for m in marks if a in ext[m:m+220])
    j = next(m for m in marks if m > i and b in ext[m:m+220])
    return ext[i:j].rstrip() + "\n"
def T(a, b):
    """slice one numbered block out of FailureTests.java"""
    return tests[tests.index(a):tests.index(b)].rstrip() + "\n"

RED = "#ff6b6b"

# ============================================================ page 01: the problem
pf = _D
rows = [("play a move", 30, [("a client names from and to", "e2 to e4, plus what to promote to"),
                             ("generate every legal move", "geometry first, king safety second"),
                             ("it is in the set: apply it", "board, rights, en passant, clock"),
                             ("flip the turn, judge it", "ACTIVE / CHECK / MATE / STALEMATE")]),
        ("take it back", 165, [("pop the last undo record", "the history is a stack of them"),
                               ("put the captured piece back", "on the square it actually stood on"),
                               ("restore rights, e.p., clock", "the undo record carries all three"),
                               ("the position is identical", "the same FEN, to the character")])]
for lab, y, boxes in rows:
    pf += _tx(88, y+31, lab, "var(--acc)", 13)
    for k, b in enumerate(boxes):
        x = 175 + k*260
        pf += _bx(x, y, 240, 54, b[0], b[1], acc=(k == 1))
        if k < 3: pf += _ar("M%s %s H%s" % (x+240, y+27, x+260), True)
pf += _ar("M555 84 V95", dash=True) + _bx(360, 95, 390, 40, "refused: the board is untouched", "", dash=True)
pf += _tx(88, 266, "read", "var(--acc)", 13)
pf += _tx(175, 266, "at any moment, without replaying the game: what are my legal moves?  is my king in check?  is it over, and how?", "var(--text)", 12, "start")
pf += _tx(615, 303, "two requests for one game at the same instant -- a double click, a retry, a second tab -- and exactly one move may land", "var(--muted)", 11.5)
P_FLOWS = _mv(1230, 320, pf)

pe = _D + '<path d="M60 40 H1180" stroke="var(--line)" stroke-width="1.5"/>'
ev = [("19:04:11  white plays e2-e4", ["20 legal moves, e2-e4 is one of them", "the lock is held about 12 microseconds",
                                       "en passant square e3, alive for one ply", "clock: white 172s, black 180s"], False),
      ("19:04:41  black plays Nb8-c6", ["the en passant square is gone again", "nothing captured: the quiet clock reads 1",
                                        "the spectators hear after the unlock"], False),
      ("19:07:02  a double click: Bf1-c4 twice", ["both requests wait on the one game lock", "the first lands and flips the turn",
                                                  "the second asks: is Bf1-c4 legal now?", "no -- it is Black's turn. Refused."], True),
      ("19:23:50  white plays Qh5xf7", ["black has zero legal moves", "and his king is attacked -> CHECKMATE",
                                        "without the check the same position", "would be STALEMATE: one primitive"], True)]
for k, (t, lines, acc) in enumerate(ev):
    x = 45 + k*295
    pe += '<circle cx="%s" cy="40" r="5" fill="var(--acc)"/>' % (x+142) + '<path d="M%s 45 V60" stroke="var(--line)"/>' % (x+142)
    pe += _card(x, 60, 285, 115, t, lines, acc=acc)
P_EX = _mv(1230, 190, pe)

REQ_HTML = '''<div class="req"><div><b>Functional requirements</b><ul>
<li>Set up a game, from the opening position or from a FEN string.</li>
<li>All six pieces' movement, including the three that everyone gets wrong: castling, en passant, promotion.</li>
<li>Enumerate every legal move for the side to move &mdash; what a board highlights and what an engine searches.</li>
<li>Play a chosen move, or refuse it; a refused move must change nothing at all.</li>
<li>After every move, say what the position is: ongoing, check, checkmate, stalemate, draw.</li>
<li>Take back the last move exactly, including the captured piece and the castling rights it destroyed.</li>
<li>Keep the move history: it is the takeback stack, the save format, and what the draw rules read.</li></ul></div>
<div><b>Non-functional requirements</b><ul>
<li>Two requests for one game must never both land: exactly one move per turn, always.</li>
<li>Bounded, not searched: "is this square attacked" is at most 64 array reads, and the king is found in O(1).</li>
<li>One generation of the legal set per ply, however many times the screen asks for it.</li>
<li>Which rules apply &mdash; draws, variants &mdash; is swappable without touching the board or the pieces.</li>
<li>A new kind of piece must not touch the board, the game, or check detection.</li>
<li>Nothing half-done: a refused move leaves the position byte-identical, and the caller can simply retry.</li>
<li>In memory, one process, no persistence (say it; a follow-up adds it).</li></ul></div></div>
'''

PROMPT = ('"Design a chess game. Two players, a real board, real rules &mdash; castling, en passant, promotion &mdash; '
          'and after every move it must tell me whether that was check, checkmate or stalemate. I want working code, '
          'not a diagram. Go."')

PROBLEM_BODY = (
 '<div class="move"><div class="prompt">' + PROMPT + '</div></div>'
 '<div class="move"><h3>The problem, in plain words</h3><p>Two people take turns moving pieces on an eight by eight '
 'board. The system exists to answer one question: <i>is this move legal?</i> And that question splits in two. Part '
 'of it is local to the piece &mdash; a bishop rides diagonals, a knight jumps, a pawn is a menagerie of special '
 'cases &mdash; and part of it is global: however correct the geometry, you may never play a move that leaves your '
 'own king under attack. Three moves break the simple picture: castling moves two pieces at once, en passant '
 'captures a pawn that is not on the square you land on, and a pawn reaching the last rank turns into something '
 'else. After every move the system must say what just happened: nothing, check, checkmate, stalemate, or a draw. '
 'The invariant that everything else hangs off is this: after a legal move, the mover\'s own king is not attacked, '
 'and after a refused move the position is exactly what it was.</p></div>'
 '<div class="move"><h3>What is expected of you in the hour</h3><p>Not a diagram: classes that compile, with a '
 '<code>main</code> that plays a real game and prints a checkmate. The interviewer watches, in this order: the '
 'questions you ask before typing (full rules or just geometry, and which draw rules, are the first two); which '
 'class owns the board; how you split geometry from king safety, because that split is the whole design; how you '
 'test a move for safety without corrupting the board; what happens when two requests arrive for the same game; '
 'where the rules that change live, so a variant is a class and not an edit; and what a refused move leaves behind. '
 'Then the twists: a made-up piece, an engine, notation, clocks, draws, and putting it on a server.</p></div>'
 '<div class="move"><h3>What the code must do</h3></div>' + P_FLOWS +
 '<div class="move"><h3>Questions to ask back, and what each answer decides</h3></div>'
 '<div class="move"><table class="ask"><tr><th>Ask</th><th>Assume this when they say "you decide"</th><th>What the answer decides</th></tr>'
 '<tr><td>Full rules &mdash; castling, en passant, promotion, checkmate &mdash; or just piece geometry?</td><td>Full rules, plus checkmate and stalemate</td><td>Whether a move is a from/to pair or a typed object that carries its own undo (moves 1, 6)</td></tr>'
 '<tr><td>Which draw rules: repetition, fifty moves, insufficient material?</td><td>Out of the base engine, added by a wrapper</td><td>The ending rules become a one-method interface, and each draw is a decorator (move 3)</td></tr>'
 '<tr><td>Two humans, or must an engine search over the same code?</td><td>Both; the engine only consumes the rules</td><td>Legal-move generation is public API, and a search runs on a copy (moves 2, 12)</td></tr>'
 '<tr><td>How do moves arrive &mdash; coordinates, or "Nf3" and "O-O"?</td><td>Coordinates; notation is a follow-up</td><td>Notation sits above the rules and never inside them (move 12)</td></tr>'
 '<tr><td>Takeback, and a full history?</td><td>Yes, and the history is needed for the draw rules anyway</td><td>A move carries what it destroyed, so undo is exact (move 6)</td></tr>'
 '<tr><td>One process and two people at one screen, or a server with two phones?</td><td>One process now; name what changes on a server</td><td>One lock per game now; a ply compare-and-set later (moves 4, 12)</td></tr>'
 '<tr><td>Clocks and time controls?</td><td>Out of scope, named</td><td>Time is injected and a clock is a listener, not a rule (moves 3, 12)</td></tr>'
 '<tr><td>How fast must legality be?</td><td>Human speed: a move every few seconds</td><td>Simulate and take back, not incremental attack maps (move 8)</td></tr></table></div>'
 '<div class="move"><h3>What it must do, and what it must survive</h3></div>' + REQ_HTML +
 '<div class="move"><h3>One game, replayed</h3></div>' + P_EX +
 '<div class="grade"><b>Say before typing:</b> full movement rules including the three special moves; checkmate and '
 'stalemate from one primitive; moves arrive as coordinates; the position is held in memory in one process, one lock '
 'per game. Named as out of scope: draw by repetition and the fifty-move rule, notation, clocks, an engine, '
 'persistence &mdash; each is a follow-up on page 05.</div>')

# ============================================================ page 02: the twelve moves
MV = {}

# move 1: nouns with state -> classes
m1 = _D + '<rect x="20" y="20" width="1190" height="44" rx="6" fill="var(--bg3)" stroke="var(--line)"/>'
m1 += _tx(615, 47, "two PLAYERS take turns moving a PIECE from one SQUARE to another on a BOARD; the GAME says whose turn it is, whether a MOVE is legal, and whether it is over", "var(--text)", 12.5)
for x, w, t, sub, acc in [(25, 165, "Game", "turn, history, status", 1), (205, 165, "Board", "64 squares + 3 facts", 1),
                          (385, 165, "Move", "what happened + its undo", 1), (565, 170, "Piece", "geometry: NO state", 0),
                          (750, 155, "Position", "two ints: a value", 0), (920, 145, "Player", "a caller", 0),
                          (1080, 130, "Status", "a question", 0)]:
    m1 += _bx(x, 110, w, 46, t, sub, acc=bool(acc), dash=not acc) + _ar("M%s 64 V110" % (x + w/2))
m1 += _tx(615, 190, "solid = it has state of its own, so it becomes a class.   dashed = no state: a value, a caller, or a question answered from state that is already there", "var(--muted)", 11)
m1 += _tx(615, 210, "the decision that pays for itself all page: a piece holds nothing -- no square, no \"has moved\" flag -- so twelve piece objects serve every game in the process", "var(--acc)", 11)
MV[1] = _mv(1230, 225, m1)

# move 2: verbs -> the class that owns the state they touch
m2 = _D + _tx(190, 21, "the verb", "var(--acc)", 11) + _tx(615, 21, "the class that owns the state it touches", "var(--acc)", 11) + _tx(1037, 21, "so it gets the method", "var(--acc)", 11)
for k, (verb, cls, meth) in enumerate([("which squares could I reach?", "Piece  (owns geometry, no state)", "piece.pseudoMoves(board, from, out)"),
                                       ("is this square attacked?", "Board  (owns the 64 squares)", "board.isAttacked(square, by)"),
                                       ("which of those are actually legal?", "Game  (owns the board AND the turn)", "game.legalMoves()"),
                                       ("play this one / take it back", "Game  (owns the history and the lock)", "game.play(move) / game.undo()")]):
    y = 32 + k*50
    m2 += _bx(25, y, 330, 40, verb) + _ar("M355 %s H420" % (y+20), True)
    m2 += _bx(420, y, 390, 40, cls, acc=True) + _ar("M810 %s H870" % (y+20), True)
    m2 += _bx(870, y, 335, 40, meth)
m2 += _tx(615, 250, "the whole design is in row 1 against row 3: a bishop knows it rides diagonals, but no piece can see whether the move exposes its own king,", "var(--muted)", 11)
m2 += _tx(615, 269, "so the piece produces PSEUDO-legal moves and the layer that owns the whole board filters them. Geometry below, king safety above.", "var(--acc)", 11)
MV[2] = _mv(1230, 284, m2)

# move 3: rules that change -> one-method interfaces handed in
m3 = _D + _tx(962, 20, "the classes that can be handed in", "var(--acc)", 11)
m3 += _bx(25, 62, 215, 90, "Game", "configure(rules); setClock(c)", acc=True)
for k, (t, sub, impl) in enumerate([("RuleSet", "when, and how, is it over?", "StandardRules / DrawRules(base) / a variant"),
                                    ("GameObserver", "who is told a move happened", "a spectator, the PGN writer, the chess clock"),
                                    ("Clock", "where the time comes from", "System::currentTimeMillis, or a test's fixed instant")]):
    y = 30 + k*56
    m3 += _ar("M240 107 H310 V%s H370" % (y+22), True, True) + _bx(370, y, 290, 44, t, sub, dash=True)
    m3 += _bx(720, y, 485, 44, impl) + _ar("M720 %s H660" % (y+22))
m3 += _bx(25, 198, 215, 44, "whoever drives the game", "your main, or the match service")
m3 += _ar("M240 220 H370", True, True) + _bx(370, 198, 290, 44, "Player", "who decides the next move", dash=True)
m3 += _bx(720, 198, 485, 44, "RandomPlayer / MinimaxPlayer", "Extensions.java: the engine on page 05") + _ar("M720 220 H660")
m3 += _tx(615, 268, "dashed green = handed in. The game is handed the first three and never builds one; Player is held by the caller, because the game does not ask for moves.", "var(--muted)", 11)
m3 += _tx(615, 288, "One rule wraps the others: DrawRules(StandardRules) adds repetition and the fifty-move rule to ANY rule set, including one written next year.", "var(--acc)", 11)
MV[3] = _mv(1230, 301, m3)

# move 4: the gap, and one owner with one lock
m4 = _D + _bx(25, 28, 205, 46, "the browser tab", "reads: white to move") + _bx(25, 112, 205, 46, "the double click", "reads: white to move")
m4 += _bx(330, 70, 195, 46, "the game", "white to move", acc=True)
m4 += _ar("M230 51 H330 V70") + _ar("M230 135 H330 V116") + _tx(280, 40, "read", "var(--muted)", 10.5) + _tx(280, 168, "read", "var(--muted)", 10.5)
m4 += '<rect x="565" y="18" width="300" height="150" rx="6" fill="none" stroke="%s" stroke-dasharray="4 3"/>' % RED
m4 += _tx(715, 44, "the gap", RED, 12) + _tx(715, 70, "both validate against the same board,", RED, 11) + _tx(715, 90, "both apply: White moves twice in a row", RED, 11)
m4 += _tx(715, 118, "chess is turn-based, so the race is never", "var(--text)", 11) + _tx(715, 138, "two players -- it is two REQUESTS", "var(--text)", 11)
m4 += _bx(900, 45, 305, 100, "Game.lock", "validate and apply = one step", acc=True)
m4 += _tx(1052, 172, "the lock lives where the board lives: one per GAME,", "var(--muted)", 10.5)
m4 += _tx(1052, 191, "so a hundred thousand games never wait for each other", "var(--muted)", 10.5)
MV[4] = _mv(1230, 205, m4)

# move 5: each collection, its question, its bounded shape
m5 = _D
for k, (q, shape, cost) in enumerate([("what is standing on e4?", "Piece[64], indexed row*8 + col", "O(1)"),
                                      ("where is the king I must protect?", "Position[2], written by board.place()", "O(1), never a scan"),
                                      ("is this square attacked?", "walk 8 rays out + 8 knight offsets", "&le; 64 reads, ~30 typical"),
                                      ("may he still castle, on which side?", "boolean[4] on the board", "O(1)"),
                                      ("can a pawn take en passant?", "one square, rewritten every single ply", "O(1)"),
                                      ("has this position happened three times?", "Map&lt;position key, count&gt;", "O(1) per ply"),
                                      ("what was the last move, and undo it", "ArrayDeque&lt;Undo&gt;", "O(1) push and pop")]):
    y = 16 + k*42
    m5 += _bx(25, y, 355, 36, q, "") + _ar("M380 %s H435" % (y+18), True)
    m5 += _bx(435, y, 510, 36, shape, "", acc=True) + _ar("M945 %s H1000" % (y+18), True) + _bx(1000, y, 205, 36, cost, "")
m5 += _tx(615, 326, "nothing here searches. The one query the whole engine leans on -- is this square attacked -- is asked from the king's square OUTWARD,", "var(--muted)", 11)
m5 += _tx(615, 345, "so a ray stops at the first piece it meets, and the answer costs at most sixty-four array reads whatever is on the board.", "var(--muted)", 11)
MV[5] = _mv(1230, 358, m5)

# move 6: the state machine and the ORDER at the critical step
m6 = _D + _bx(25, 30, 175, 42, "ACTIVE", "moves accepted", acc=True) + _bx(255, 30, 175, 42, "CHECK", "moves accepted", acc=True)
m6 += _bx(25, 112, 175, 42, "CHECKMATE", "terminal") + _bx(175, 178, 175, 42, "STALEMATE", "terminal") + _bx(325, 112, 175, 42, "DRAW", "terminal")
m6 += _ar("M200 43 H255", True) + _ar("M255 62 H200", True) + _ar("M112 72 V112", True) + _ar("M300 72 V178", True) + _ar("M412 72 V112", True)
m6 += _tx(285, 264, "no legal move + in check = CHECKMATE.   no legal move, not in check = STALEMATE.", "var(--muted)", 10.5)
m6 += _tx(285, 283, "one primitive, two endings, so the two can never drift apart.", "var(--muted)", 10.5)
m6 += _tx(285, 306, "every arrow is one ply, and a status always describes the side about to move:", "var(--acc)", 10.5)
m6 += _tx(285, 324, "ACTIVE -> CHECKMATE is White, not in check, playing the move that mates Black.", "var(--acc)", 10.5)
m6 += '<rect x="560" y="20" width="650" height="222" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(885, 44, "the order inside play(), and why it is this order", "var(--text)", 12)
for k, l in enumerate(["1  refuse outright if the game is already over",
                       "2  generate the legal set HERE: a screen that offers legal moves is a convenience, not a rule",
                       "3  only now edit the board, and push the record that can undo that edit",
                       "4  flip the turn, re-judge the position: the parts a caller can observe change last",
                       "5  release the lock, and only then tell the spectators",
                       "the board edit at step 3 is the one thing that happens before the game is committed,",
                       "and it is the one edit we know how to take back exactly. So a refusal at step 1 or 2",
                       "leaves the board, the turn and the history untouched, and the caller can simply retry."]):
    m6 += _tx(575, 68 + k*22, l, "var(--muted)" if k > 4 else "var(--text)", 11, "start")
MV[6] = _mv(1230, 338, m6)

# move 7: what is inside the lock, and eight clients at the same instant
m7 = _D + _card(25, 20, 555, 126, "inside the lock: about 12 microseconds, measured",
                ["generate ~35 candidate moves from the geometry", "for each: apply it, ask if my king is attacked, take it back",
                 "one attack question is at most 64 array reads", "apply the winner, push the undo record, flip the turn",
                 "judge the new position (which reuses that generation)"], acc=True)
m7 += _ar("M580 83 H645", True) + _tx(612, 73, "unlock", "var(--acc)", 10.5)
m7 += _card(645, 20, 560, 126, "outside the lock: milliseconds to minutes",
            ["the spectator's websocket frame: about 1 millisecond", "writing the move to a database: about 5 milliseconds",
             "an engine searching for its reply: 100 ms and up", "the human staring at the board: three seconds, or three days"])
m7 += _tx(615, 176, "eight clients press at the same instant (a double click, a retry, two tabs, a reconnect)", "var(--text)", 12)
for k in range(8):
    x = 25 + k*148
    m7 += _bx(x, 190, 136, 42, "request %d" % (k+1), "waits %s us" % (k*12), acc=(k == 0))
m7 += _tx(615, 258, "the eighth waits eighty-four microseconds for the lock -- and then is refused in a microsecond, because by then it is Black's turn", "var(--muted)", 11)
m7 += _tx(615, 277, "and its move is a White move, which is not in the legal set. One at a time is true, and at these numbers nobody can tell.", "var(--muted)", 11)
MV[7] = _mv(1230, 290, m7)

# move 8: the arithmetic, then the ladder
m8 = _D + '<rect x="20" y="20" width="560" height="190" rx="6" fill="var(--bg3)" stroke="var(--line)"/>' + _tx(300, 42, "one lock per game: is it a bottleneck? do the arithmetic", "var(--text)", 12)
for k, l in enumerate(["a whole play(): about 12 microseconds, measured in Main",
                       "blitz is a move every three seconds, per player",
                       "so one game's lock is busy 12 us in every 3,000,000 us",
                       "that is four ten-thousandths of one per cent",
                       "100,000 live games = 33,000 moves a second = 0.4 of one core",
                       "and no two games ever contend, because the lock is per game"]):
    m8 += _tx(35, 66 + k*24, l, "var(--muted)", 11, "start")
m8 += _tx(895, 42, "the upgrade ladder, in the order you would climb it", "var(--text)", 12)
for k, (t, sub) in enumerate([("1  generate the legal set once per ply", "already done: the status check and the next move share it"),
                              ("2  only test moves that CAN be illegal", "find the pins once; king moves and evasions; ~10x fewer checks"),
                              ("3  bitboards: the position as twelve longs", "a rook's attacks become one table lookup. Stockfish. ~100x")]):
    m8 += _bx(600, 58 + k*52, 605, 44, t, sub, acc=(k == 0))
m8 += _tx(615, 232, "say the arithmetic first. Rung 3 is the famous answer and the wrong one here: two humans move every three seconds, and a hundredfold", "var(--muted)", 11)
m8 += _tx(615, 251, "speed-up on a lock that is idle 99.9996% of the time buys nothing. Rung 3 is for an engine searching millions of positions, and you say so.", "var(--muted)", 11)
MV[8] = _mv(1230, 265, m8)

# move 9: what can go wrong, and the test for each
m9 = _D
for k, (bad, fix) in enumerate([("a move that leaves my own king in check", "apply it, ask, take it back; test 3: a pinned bishop has ZERO legal moves"),
                                ("mutating to simulate, and not putting it back", "undo is the exact mirror; test 4: the FEN is identical after generating everything"),
                                ("a pawn's forward move reused as its attack", "attacks() and pseudoMoves() are separate; test 8: a pawn ahead of a king is no check"),
                                ("castling out of, through, or into check", "five conditions, checked in the rules layer; test 5: f1 attacked, O-O refused"),
                                ("en passant claimed one ply too late", "the square is rewritten every ply; test 6: the window is exactly one ply"),
                                ("checkmate and stalemate drifting apart", "one primitive, split by check; test 8: fool's mate and a real stalemate"),
                                ("two requests for one game at one instant", "one lock per game; test 9: 50 threads, exactly 1 move lands")]):
    y = 16 + k*40
    m9 += _bx(25, y, 355, 34, bad, "") + _ar("M380 %s H425" % (y+17), True) + _bx(425, y, 780, 34, fix, "", acc=True)
m9 += _tx(615, 314, "and the one that proves the lot: perft, the published leaf counts of the legal-move tree. 20, 400, 8902, 197281 from the opening position,", "var(--acc)", 11)
m9 += _tx(615, 333, "plus three standard positions built to catch castling, en passant, promotion and pin bugs. Test 2 reproduces every number exactly.", "var(--muted)", 11)
MV[9] = _mv(1230, 346, m9)

# move 10: the patterns, named after the fact
cols10 = [("pattern", 12), ("born in", 200), ("the line in the code", 290), ("what it buys", 830)]
rows10 = [[("Template Method", "var(--text)"), ("move 2", None), ("SlidingPiece walks the rays; Rook, Bishop, Queen supply only vectors", None), ("one ray walk, not three copies", None)],
          [("Strategy", "var(--text)"), ("move 3", None), ("interface RuleSet { adjudicate(game, inCheck, anyLegalMove) }", None), ("a variant is a class, not an edit", None)],
          [("Decorator", "var(--text)"), ("move 3", None), ("new DrawRules(new StandardRules()) -- and stack another on top", None), ("one draw rule per wrapper", None)],
          [("Observer", "var(--text)"), ("move 4", None), ("publish(move, after) after the unlock, inside a try/catch", None), ("a broken spectator cannot break chess", None)],
          [("Command", "var(--text)"), ("move 6", None), ("Undo carries the victim, the rights, the e.p. square, the clock", None), ("takeback and the filter are one mechanism", None)],
          [("State", "var(--text)"), ("move 6", None), ("ACTIVE / CHECK / CHECKMATE / STALEMATE / DRAW, judged once a ply", None), ("a finished game refuses every move", None)],
          [("Flyweight", "var(--text)"), ("move 1", None), ("Pieces.of(color, letter): twelve objects for the whole process", None), ("a stateless piece cannot be half-undone", None)],
          [("Factory", "var(--muted)"), ("not yet", None), ("Pieces.register('C', Chancellor::new) IS the registry, one line", "var(--muted)"), ("it earns the name when variants ship sets", "var(--muted)")],
          [("Singleton", "var(--muted)"), ("not here", None), ("a Game is built by its caller; nothing calls getInstance()", "var(--muted)"), ("a test builds a fresh game per case", "var(--muted)")],
          [("Builder", "var(--muted)"), ("never", None), ("a Move's seven fields are all decided by one generator", "var(--muted)"), ("nobody hand-builds a Move; it would be ceremony", "var(--muted)")]]
m10 = _D + _table(20, 16, cols10, rows10, rowh=29, widths=1190)
m10 += _tx(615, 358, "name a pattern only after the move that produced it; then every name has a one-sentence defence and none of them is decoration", "var(--muted)", 11)
MV[10] = _mv(1230, 372, m10)

# move 11: SOLID as a check on the moves
cols11 = [("", 12), ("the rule, in plain words", 48), ("from", 430), ("the line that shows it", 540)]
rows11 = [[("S", "var(--acc)"), ("one reason to change per class", None), ("move 2", None), ("Piece: geometry. Board: the squares and \"is this attacked\". Game: turn, legality, status.", None)],
          [("O", "var(--acc)"), ("new behaviour is a new class, not an edited one", None), ("moves 1, 3", None), ("a Chancellor is one class and one register() line: Board and Game do not change", None)],
          [("L", "var(--acc)"), ("any implementation drops in; nobody checks which", None), ("move 1", None), ("the engine only ever calls pseudoMoves, attacks and the flags -- never \"is this a rook?\"", None)],
          [("I", "var(--acc)"), ("small interfaces: one real method each", None), ("move 3", None), ("RuleSet, Player, GameObserver, Clock: one method each, so a fake is a lambda", None)],
          [("D", "var(--acc)"), ("depend on interfaces; implementations are handed in", None), ("moves 3, 9", None), ("game.configure(new DrawRules(base, 6, 99)) is why the fifty-move test is six plies long", None)]]
m11 = _D + _table(20, 18, cols11, rows11, rowh=34, widths=1190)
m11 += _tx(615, 248, "SOLID is not a list to recite; it is the check that the moves did their job, one line each", "var(--muted)", 11)
MV[11] = _mv(1230, 262, m11)

# move 12: every twist is one of five moves
m12 = _D
for k, (t, sub, fix, sub2, mv) in enumerate([
        ("a new rule", "a fairy piece, a variant, a house rule", "a new class behind Piece, or behind RuleSet, plus one line", "", "moves 1, 3"),
        ("someone new wants to know", "a PGN writer, a clock, a rating update", "one more observer; the board and the lock do not change", "", "move 4"),
        ("a new step in a life", "resignation, a draw offer, a flag-fall", "one more status and one more checked transition", "", "move 6"),
        ("a new invariant across the whole history", "threefold repetition, the fifty-move rule", "counted in the SAME critical section as the move, so it cannot drift", "", "moves 4, 5"),
        ("state that must outlive the process", "two servers; a phone that reconnects", "the move list behind a repository, and the lock becomes", "play(expectedPly, move)  ->  UPDATE games SET ... WHERE ply = ?", "moves 5 + 12")]):
    y = 20 + k*54
    m12 += _bx(25, y, 350, 44, t, sub) + _ar("M375 %s H430" % (y+22), True) + _bx(430, y, 660, 44, fix, sub2, acc=True) + _tx(1150, y+27, mv, "var(--muted)", 11)
m12 += _tx(615, 308, "for all five the Board, the Piece classes and the tests do not change; that is the test that the derivation was right", "var(--muted)", 11)
MV[12] = _mv(1230, 322, m12)

MOVES = [
("Move 1: underline the nouns. Every noun with its own state becomes a class.",
 "The picture is that sentence with its nouns underlined, and the boxes are the answer. Two of them are worth "
 "arguing about. A <b>board</b> is not just sixty-four squares: it also holds the three facts a naive design forgets "
 "&mdash; who may still castle, which square is capturable en passant, and how many quiet plies have passed &mdash; "
 "because every one of them changes with a move and has to be put back by a takeback. And a <b>piece holds no state "
 "at all</b>: not its square, not a \"has moved\" flag. Castling rights live on the board, where move generation can "
 "see them anyway. That single decision pays for itself all page: twelve piece objects serve every game in the "
 "process, and a takeback can never leave a piece half-restored, because there is nothing on a piece to restore.", 1),
("Move 2: for every verb, ask which class holds the state it touches. That class gets the method.",
 "Read the first row against the third, because that pair is the whole design. A bishop knows perfectly well that it "
 "rides diagonals, and it cannot possibly know whether riding one exposes its own king &mdash; no piece can see the "
 "whole board. So a piece produces <i>pseudo-legal</i> moves, geometry only, and the layer that owns the whole board "
 "filters them for king safety. Geometry below, king safety above. Every hard thing in chess &mdash; check, "
 "checkmate, pins, castling through an attacked square &mdash; falls out of that one line, and blurring it is the "
 "most common way a chess design collapses at minute forty.", 2),
("Move 3: every rule the interviewer can change mid-round goes behind an interface and is handed in.",
 "Which endings count will change: checkmate and stalemate today, the fifty-move rule and threefold repetition the "
 "moment they ask, insufficient material after that, a variant if they are feeling playful. Who decides a move will "
 "change: a human today, a random mover in a test, an alpha-beta search by the end of the hour. Who is told will "
 "change: a spectator today, a move list, a clock, a rating update. And where time comes from must change, or a clock "
 "cannot be tested. Each becomes a one-method interface that nobody inside the game builds: three are handed to "
 "the game itself, in <code>configure()</code> and <code>setClock()</code>, and the fourth, <code>Player</code>, is "
 "held by whoever drives the game &mdash; your <code>main</code>, or the match service &mdash; because the game "
 "never asks anyone for a move, it is told one. This is where the patterns come from, not the other way round: a swappable rule behind an interface "
 "is <b>Strategy</b>; a rule that wraps another rule and adds to it is <b>Decorator</b>, and here it is the one that "
 "matters &mdash; <code>DrawRules(StandardRules)</code> adds repetition and the fifty-move rule to <i>any</i> rule "
 "set, so the same wrapper works over ordinary chess and over a variant written next year, and you can stack "
 "insufficient material on top without either knowing the other exists. A game that announces \"a move landed\" "
 "without knowing what a websocket is, is <b>Observer</b>. I do them; I do not announce them.", 3),
("Move 4: state that many callers change at the same time gets one owner and one lock.",
 "Say out loud first that chess is turn-based, so the race is <i>never</i> two players &mdash; it is two "
 "<b>requests</b> for the same player. Both read \"White to move\", both generate the same legal set, both find "
 "their move in it, and both apply: White has now moved twice in a row and the board is quietly, permanently wrong. "
 "So validating and applying must be one step, in the class that owns the board and the turn: the game. The lock is "
 "per <i>game</i>, not per server, which is the whole trick &mdash; a hundred thousand live games take a hundred "
 "thousand different locks and never wait for each other. Anything that only listens (the websocket, the database "
 "write) is called after the lock is released, inside a try/catch, so a broken spectator cannot break chess.", 4),
("Move 5: for each collection, ask what question is asked of it, and pick the shape that answers without searching.",
 "Two rows are decisions, not data structures. \"May he still castle?\" is four booleans <i>on the board</i>, not a "
 "flag on a rook &mdash; which is also why a rook captured on its own corner correctly kills that right, with no "
 "special case written anywhere. \"Can a pawn take en passant?\" is a single square, rewritten on <i>every</i> ply, "
 "because that is exactly how long the chance lives; forgetting to clear it is the classic en passant bug. Then the "
 "query the whole engine leans on, \"is this square attacked?\", which is asked from the king's square "
 "<b>outward</b>: walk the eight rays until the first piece and ask it what it can do, then the eight knight offsets. "
 "At most sixty-four array reads whatever is on the board, usually about thirty, because a ray stops at the first "
 "piece it meets &mdash; against roughly eighteen hundred for the obvious version that scans all sixty-four squares "
 "and enumerates every enemy piece's attacks. And it asks each piece what it <i>can do</i>, never what it <i>is</i>, "
 "which is why a made-up piece that rides straight lines is detected here with no edit at all.", 5),
("Move 6: anything with a life cycle is a state machine, and the order of operations is part of the design.",
 "ACTIVE and CHECK both still accept moves; CHECKMATE, STALEMATE and DRAW are terminal and refuse everything. Write "
 "that down and the classic bug disappears: checkmate and stalemate are not two detectors that will drift apart, they "
 "are one condition &mdash; \"the side to move has no legal move\" &mdash; split by whether that side is in check. "
 "The panel on the right is the order inside <code>play</code>, which is the part the interviewer is really asking "
 "about, and its reason is one sentence: the board edit at step 3 is the only thing that happens before the game is "
 "committed, and it is the one edit we know how to take back exactly. Which is also why generating the legal set is "
 "safe at all &mdash; it plays each candidate on the real board, asks whether the king is now attacked, and takes it "
 "back. The same mechanism as a takeback, which is why it is the best-tested code in the file.", 6),
("Move 7: yes, the lock makes one game's moves happen one at a time. Ask for how long, and what is inside it.",
 "The picture lists what is inside; the number is the answer. <code>Main</code> plays fifteen hundred plies of random "
 "games and times them: about twelve microseconds for the whole of generate, filter, commit, re-judge. Everything "
 "slow is outside &mdash; the websocket frame, the database write, an engine's hundred milliseconds, a human's three "
 "seconds &mdash; because the lock is released before any of them is called. So when eight requests land at the same "
 "instant the eighth waits about eighty-four microseconds, and is then refused in one more, because by then it is "
 "Black's turn and the White move it is holding is not in the legal set. Waiting is not the cost worth worrying "
 "about here; being wrong about whose turn it is would be.", 7),
("Move 8: say the arithmetic, then name the ladder.",
 "Twelve microseconds of lock against blitz, which is a move every three seconds: one game's lock is busy twelve "
 "microseconds in every three million, four ten-thousandths of one per cent. A hundred thousand live games is "
 "thirty-three thousand moves a second, four tenths of one core, and no two games ever contend because the lock is "
 "per game. That arithmetic, not the ladder, is the answer to \"does one lock scale\". The ladder is what you say "
 "next. Rung one is already in this code. Rung two is the only real algorithmic win, and it is worth knowing why it "
 "works: a move can be illegal for exactly three reasons &mdash; the piece is pinned to its king, the king itself is "
 "walking, or you are already in check &mdash; so find the pins once by walking eight rays out from the king, and the "
 "other thirty moves are legal by construction rather than by test. About ten times fewer attack questions. Rung "
 "three, bitboards, is the famous answer and the wrong one here: a hundredfold speed-up on a lock that is idle "
 "99.9996 per cent of the time buys nothing. It is for an engine searching millions of positions a second, and you "
 "say exactly that.", 8),
("Move 9: list what can go wrong, and write the test for each before the interview is over.",
 "The table is the checklist; three rows are worth saying out loud. A pawn's forward move is not its attack, and a "
 "generator that reuses one for the other makes check detection silently wrong in a way no ordinary game shows you: "
 "a pawn directly in front of a king gives no check, one file over it does, and test 8 pins both of those down. "
 "Simulating by mutating the real board is safe only if the undo is an exact mirror, so test 4 generates every legal "
 "move in six positions &mdash; one of them full of pins and castling rights &mdash; and checks the FEN is identical "
 "to the character afterwards. And then the one that proves the lot: <b>perft</b>, the published leaf counts of the "
 "legal-move tree &mdash; 20, 400, 8902, 197281 from the opening position, plus three standard positions built "
 "specifically to catch castling, en passant, promotion and pin bugs. There is no way to be accidentally correct at "
 "197281, which makes it the one claim in chess you can prove rather than argue.", 9),
("Move 10: now, and only now, name the patterns. Each one is the result of a move.",
 "The table is the answer; the rule behind it is what to say. Name a pattern only after the move that produced it, "
 "and every name arrives with a one-sentence defence instead of a claim. Two rows deserve a breath more. "
 "<b>Flyweight</b> was earned, not chosen: twelve piece objects can be shared only because move 1 decided a piece "
 "holds no state, and a single \"has moved\" flag on a rook would cost you both the sharing and the exact takeback. "
 "<b>Decorator</b> is the one an interviewer will push on: <code>DrawRules</code> wraps any rule set and insufficient "
 "material stacks on top of that, each wrapper knowing one rule and nothing about the others, which is precisely what "
 "lets a draw rule be added in the middle of the round. And the bottom three rows earn their space as much as the top "
 "seven: a pattern with no move behind it is decoration, which is the whole answer to \"why no Factory?\".", 10),
("Move 11: run SOLID as a check on the moves, one line each.",
 "The table is a check, not a recital, and two of its rows are things you can demonstrate rather than assert. "
 "<b>O</b>: a brand-new piece is one class and one <code>register</code> line, and you can show the board, castling, "
 "check detection and checkmate all still working in ninety seconds when they invent a fairy piece. <b>D</b>: the "
 "fifty-move test is six plies long instead of a hundred moves, because the test hands in "
 "<code>new DrawRules(base, 6, 99)</code> &mdash; only possible because the game is handed its rules and never builds "
 "them. If a letter has no line in the last column, the moves did not do their job.", 11),
("Move 12: every twist the interviewer adds is one of five moves. Say which before you type.",
 "Naming which of the five it is, out loud, before you type, is most of the answer. Two of the rows hide a decision "
 "worth making in front of them. <b>Resignation and a draw offer</b> are row three done properly: one more terminal "
 "status and one more checked transition, so a resigned game refuses moves exactly the way a checkmated one does. A "
 "<b>flag-fall</b> looks like the same thing and is not: the rules engine has no business knowing there is a clock, "
 "so the <i>service</i> checks the time before it accepts a move and records a loss on time itself &mdash; which is "
 "why one rules engine serves a bullet game and a correspondence game. And row four is the one people get wrong: a "
 "new invariant across the whole history is counted inside the <i>same</i> critical section as the move, so the count "
 "and the position can never disagree. For all five the board, the piece classes and the tests do not change; that is "
 "the test that the derivation was right, and page 05 has the code for each.", 12),
]
DERIVATION_LEAD = ("Run these on any LLD (parking lot, elevator, Splitwise) and the class diagram, the lock, the tests, "
 "the patterns, SOLID and the answer to every twist fall out in that order; nothing is chosen up front, and nothing is "
 "named before the move that produced it. On chess the moves earn their keep at move 2, because the one thing that "
 "makes this problem hard -- that legality is half local to a piece and half global to the board -- is exactly what "
 "asking \"which class owns the state this verb touches\" tells you.")

# ============================================================ page 03: the class diagram
uml_reset()
# column A: the callers, the handed-in interfaces, the values
put("svc", 10, 20, 240, "ChessService", ["games: Map&lt;id, Game&gt;"], ["newGame(id): Game", "game(id): Game"])
put("player", 10, 130, 240, "Player", [], ["choose(game): Move", "Extensions.java, with the engine"], "interface")
put("obs", 10, 215, 240, "GameObserver", [], ["onMove(game, move, after)"], "interface")
put("logger", 10, 296, 240, "MoveLogger", [], ["prints each move and its status"])
put("clock", 10, 368, 240, "Clock", [], ["nowMs(): long"], "interface")
put("pos", 10, 443, 240, "Position", ["row: int,  col: int"], ["at(row, col) / of(\"e4\")"])
put("move", 10, 538, 240, "Move", ["from / to: Position", "moved / captured: Piece", "capturedAt: Position", "kind: MoveKind", "promoteTo: Piece"],
    ["isCapture(): boolean"])
put("undo", 10, 696, 240, "Undo", ["move: Move", "enPassantBefore: Position", "rightsBefore: boolean[4]", "halfmoveBefore: int"], [])
# column B: the aggregate root and the board it owns
put("game", 285, 20, 330, "Game",
    ["id: String", "board: Board", "toMove: Color", "status: GameStatus", "history: Deque&lt;Undo&gt;",
     "seen: Map&lt;position key, count&gt;", "lock: ReentrantLock", "rules: RuleSet,  clock: Clock",
     "observers: List&lt;GameObserver&gt;", "cachedLegal: List&lt;Move&gt;"],
    ["configure(rules) / setClock(c)", "legalMoves(): List&lt;Move&gt;", "play(move): GameStatus",
     "play(expectedPly, move)", "undo(): Move", "status() / winner() / ply()", "history() / fen()"])
put("ime", 285, 715, 330, "IllegalMoveException", [], ["thrown by play() before it writes", "anything: the board is untouched"])
put("board", 285, 385, 330, "Board",
    ["squares: Piece[64]", "kings: Position[2]", "enPassantTarget: Position", "rights: boolean[4]", "halfmove: int"],
    ["at(p) / place(p, piece) / remove(p)", "kingOf(color): Position", "isAttacked(square, by): boolean",
     "inCheck(color): boolean", "fromFen(s) / toFen(...)", "positionKey(toMove): String"])
# column C: the enums and the rules that are handed in
put("color", 650, 20, 250, "Color", ["WHITE, BLACK"], ["opponent() / forward()", "pawnRow() / lastRow()"], "enum")
put("kind", 650, 130, 250, "MoveKind", ["NORMAL, DOUBLE_PAWN,", "EN_PASSANT, PROMOTION,", "CASTLE_KING, CASTLE_QUEEN"], [], "enum")
put("status", 650, 240, 250, "GameStatus", ["ACTIVE, CHECK, CHECKMATE,", "STALEMATE, DRAW"], ["over(): boolean"], "enum")
put("rules", 650, 355, 250, "RuleSet", [], ["adjudicate(game, inCheck,", "  anyLegalMove): GameStatus"], "interface")
put("std", 650, 450, 250, "StandardRules", [], ["no move + check = MATE", "no move, no check = STALE"])
put("draw", 650, 540, 250, "DrawRules", ["base: RuleSet (wrapped)"], ["fifty quiet plies = DRAW", "third repetition = DRAW"])
put("pieces", 650, 655, 250, "Pieces", [], ["of(color, letter): Piece", "register(letter, maker)", "promotionChoices(color)"])
# column D: the piece hierarchy
put("piece", 935, 20, 285, "Piece", ["color: Color"],
    ["attacks(board, from, out)", "pseudoMoves(board, from, out)", "ridesStraight() / ridesDiagonal()",
     "hopsKnight() / stepsOne()", "attacksPawnwise()", "isPawn() / isKing() / symbol()"], abstract=True)
put("slide", 935, 215, 285, "SlidingPiece", ["dirs: int[][]"], ["attacks = walk each ray until", "the edge or the first piece"], abstract=True)
put("rook", 935, 340, 135, "Rook", [], ["4 straight rays"])
put("bishop", 1085, 340, 135, "Bishop", [], ["4 diagonals"])
put("queen", 935, 415, 285, "Queen", [], ["both sets of rays: nothing new"])
put("knight", 935, 490, 135, "Knight", [], ["8 fixed jumps"])
put("king", 1085, 490, 135, "King", [], ["the 8 neighbours"])
put("pawn", 935, 565, 285, "Pawn", [], ["attacks: two diagonals", "moves: one, two, take, e.p., promote"])
put("chan", 935, 665, 285, "Chancellor", [], ["rook rays + knight hops", "Extensions.java: one new class", "and one register() line"])

def wire(x1, y1, x2, y2):
    """a plain segment of an inheritance bus: no arrowhead, the bus carries one at its end"""
    return '<path d="M%s %s L%s %s" fill="none" stroke="var(--muted)" stroke-width="1.3"/>' % (x1, y1, x2, y2)

EDGES = [
 # the three sliding pieces meet on one bar and inherit once
 ln(B["slide"]["t"], B["piece"]["b"], "inherit"),
 wire(1002, 340, 1002, 322), wire(1152, 340, 1152, 322), wire(1077, 415, 1077, 322), wire(1002, 322, 1152, 322),
 ln((1077, 322), (1077, 305), "inherit"),
 # the four that do not slide run down one bus to the left of the column
 wire(935, 517, 922, 517),                                   # Knight
 wire(1152, 490, 1152, 478), wire(1152, 478, 922, 478),      # King, below the Queen
 wire(935, 600, 922, 600),                                   # Pawn
 wire(935, 708, 922, 708),                                   # Chancellor, from Extensions.java
 wire(922, 708, 922, 145),
 ln((922, 145), (935, 145), "inherit"),
 # the rules: StandardRules straight up, DrawRules around the right, and it wraps one too
 ln(B["std"]["t"], B["rules"]["b"], "inherit"),
 ln((900, 585), (900, 410), "inherit", "", [(910, 585), (910, 410)]),
 _tx(770, 533, "wraps any RuleSet, even a wrapper", "var(--acc)", 10.5),
 _tx(775, 762, "the twelve shared Piece objects live here", "var(--muted)", 10.5),
 # what the game owns, references and is handed
 ln(B["game"]["b"], B["board"]["t"], "compose", "the one board"),
 ln((285, 300), (250, 745), "compose", "", [(278, 300), (278, 745)]),
 ln(B["board"]["r"], (935, 120), "assoc", "", [(628, 494), (628, 120)]),
 ln((615, 300), (650, 390), "inject", "", [(640, 300), (640, 390)]),
 ln(B["logger"]["t"], B["obs"]["b"], "inherit"),
 _tx(775, 347, "handed in through configure()", "var(--acc)", 10.5),
 # the band under the board: what the two composition arrows mean, in words
 _tx(450, 648, "the game owns the one board and every undo record,", "var(--muted)", 11),
 _tx(450, 670, "and holds the one lock. The board's sixty-four slots", "var(--muted)", 11),
 _tx(450, 692, "hold references to the twelve shared piece objects.", "var(--muted)", 11),
 ln((285, 100), (250, 242), "notify", "", [(262, 100), (262, 242)]),
 ln((285, 130), (250, 395), "inject", "", [(270, 130), (270, 395)]),
 ln(B["svc"]["r"], (285, 60), "compose", ""),
 ln(B["player"]["r"], (285, 80), "assoc", "", [(254, 165), (254, 80)]),
 ln((130, 696), (130, 676), "assoc", ""),
 ln((130, 538), (130, 517), "assoc", ""),
]
UMLSVG = uml_svg(1230, 860, EDGES, legend_y=835)

HOW_TO_READ = ('<b>How to read a box.</b> Top: the class name (<i>italic</i> = abstract, never instantiated; dashed '
 'border = interface; &laquo;enum&raquo; = a fixed list of values). Middle: its fields, the state it holds. Bottom: '
 'its methods. <b>The arrows.</b> Hollow triangle = extends or implements. Filled diamond = owns: the game owns the '
 'one board and every undo record. Plain arrow = references: the board\'s sixty-four slots hold piece references, and '
 'a move points at two positions. Dashed green = handed in through <code>configure()</code>. Dotted blue = '
 'notifies. <b>Where state lives:</b> the board has the squares, the king cache, the castling rights, the en passant '
 'square and the fifty-move clock, and nothing else caches any of them; the game has the turn, the history, the '
 'status, the repetition counts, the handed-in rules and the one lock; a move has what it destroyed, which is what '
 'makes a takeback exact. Notice what is <i>not</i> here: <b>no state on a piece at all</b> &mdash; no square, no '
 '"has moved" flag &mdash; which is why twelve piece objects serve every game in the process and why the whole right '
 'column is pure geometry. And no Rules class scattered about: castling is generated in the game, because it is the '
 'one move whose legality depends on squares being attacked, which no piece can see. Two boxes are here because '
 'they are in Main.java and you will type them: <b>MoveLogger</b> is the one spectator the demo installs, and '
 '<b>IllegalMoveException</b> is what a refused move throws &mdash; thrown before anything is written, which is why '
 'a refusal leaves the position exactly as it was. <b>Player</b> and <b>Chancellor</b> say Extensions.java on them: '
 'they arrive with the follow-ups on page 05, not in the hour.')

# ============================================================ page 04: the code
CODE_INTRO = ('Read it with page 03 open in a second tab if you want the diagram beside it. The green comment above '
 'each class and method says what it does; read only those first for the shape, then the bodies for the mechanics. '
 'Each copy button copies that whole file for your IDE. Below Main.java: Extensions.java (every follow-up\'s '
 'reference code, with an <code>ExtDemo</code> main that runs all of it) and FailureTests.java (ten claims proven, '
 'including the published perft counts; <code>javac Main.java Extensions.java FailureTests.java &amp;&amp; java '
 'FailureTests</code> prints ALL PASS).')

# ============================================================ page 05: follow-ups and practice
IMPLEMENT_CARD = ('<div class="card"><div class="ch"><h3>0 &middot; Implement the system</h3>'
 '<button class="timer" data-min="60">start 60:00</button></div><div class="cb"><div class="prompt">' + PROMPT + '</div>'
 'Before typing, write your six to eight clarifying questions (full rules or geometry only, and which draw rules, '
 'first); then type in the order of Main.java: the three enums and Color\'s four helpers, Position, the abstract '
 'Piece with its one geometry method and its capability flags, SlidingPiece and the six pieces, the Pieces registry, '
 'Move and Undo, Board with isAttacked and FEN, the RuleSet interface with StandardRules, then Game with its lock, '
 'its legal-move filter and the order inside play, then the thin service, then a main with fifty threads.</div></div>')

FU = [
("The interviewer invents a piece: a Chancellor, which moves like a rook AND a knight. How much of your code changes?",
 "twist", 8,
 "One new class and one line. The Chancellor extends Piece, walks the four straight rays and adds the eight knight "
 "squares, and says yes to two capability questions: do you ride straight lines, do you hop like a knight. Move "
 "generation already works, because everything calls <code>pseudoMoves</code> on the abstraction. Check detection "
 "already works, and this is the part worth pointing at: <code>isAttacked</code> walks outward from the king and asks "
 "each piece it meets what it <i>can do</i>, never what it <i>is</i>, so a chancellor sitting on a rank is found by "
 "the ray probe and one sitting on a knight square is found by the jump probe. Castling, checkmate, stalemate, FEN, "
 "printing and promotion all keep working untouched. The registry line is the only edit outside the new file.",
 X("a fairy piece", "an AI opponent")),
("Two requests arrive for the same game at the same instant -- a double click, or a phone retrying. Prove you cannot play two moves on one turn.",
 "non-functional", 10,
 "The race lives between generating the legal set and applying the chosen move. <code>play</code> does both inside "
 "one lock held by the game, so no second request can slip into that gap. The proof is not a count but the rules "
 "themselves: fifty threads wait on one latch and all fifty fire an opening move at the same game, and afterwards "
 "exactly one was accepted, the history has exactly one ply and the turn flipped exactly once. The forty-nine losers "
 "were not refused by the lock &mdash; they waited for it politely and were then refused by chess, because by the "
 "time they got in it was Black's turn and a White move is not in the legal set. The same test then plays eight whole "
 "games in parallel to show the lock is per game and they never touch.",
 T("        // 9. two requests for one game", "        // 10. the draw rules")),
("One lock per game. Have you just serialised your chess server?",
 "non-functional", 5,
 "No, and the answer is arithmetic rather than opinion. A whole <code>play</code> is about twelve microseconds; "
 "<code>Main</code> times fifteen hundred plies of random games to get that number. Blitz is a move every three "
 "seconds, so one game's lock is busy twelve microseconds in every three million &mdash; four ten-thousandths of one "
 "per cent &mdash; and a hundred thousand live games is thirty-three thousand moves a second, four tenths of one "
 "core, with no two games ever contending because the lock is per game and not per server. Then the ladder, if they "
 "push: the legal set is already generated once per ply and remembered; then test only the moves that can possibly be "
 "illegal (pinned pieces, king moves, check evasions), about ten times fewer attack questions; then bitboards, worth "
 "a hundredfold to an engine and worth nothing at all to two humans moving every three seconds.",
 sect(src, "    GameStatus play(Move move)", "    /**\n     * Take back the last move")),
("A move turns out to be illegal. What is the state of the board?",
 "functional", 8,
 "Exactly what it was, character for character. Nothing is written until the move has been found in the legal set, "
 "and the legal set is built by playing each candidate on the real board, asking the one question that matters, and "
 "taking it back &mdash; so the only edits that happen before a decision are edits we can reverse exactly. The undo "
 "record carries what a move quietly destroys: the captured piece and the square it actually stood on, the four "
 "castling rights, the en passant square and the fifty-move clock. That is why taking back a move is the same code as "
 "filtering for legality, and why it is the best-tested code in the file: the test generates every legal move in six "
 "positions, including one full of pins and castling rights, and checks that the FEN is identical afterwards. If they "
 "ask for redo as well, it is the same records pushed the other way &mdash; a second stack that <code>undo</code> "
 "pushes onto and <code>play</code> clears &mdash; and no new mechanism at all.",
 sect(src, "    private List<Move> legalMovesLocked()", "    /** Ask the rule set")),
("The board highlights legal squares on every click, and the search asks a hundred thousand times a second. Make \"is my king in check\" cheap.",
 "non-functional", 5,
 "Two things, neither of them a new data structure. First, finding the king is a two-slot cache the board writes "
 "whenever a king is placed, so it is one array read instead of a sixty-four-square hunt done once per candidate "
 "move. Second, the attack question is asked from the king's square <i>outward</i>: walk the eight rays until the "
 "first piece and ask that piece what it can do, then check the eight knight offsets. At most sixty-four array reads "
 "whatever is on the board, usually about thirty, because a ray stops at the first piece it meets &mdash; against "
 "roughly eighteen hundred for the obvious version that scans all sixty-four squares and enumerates every enemy "
 "piece's attacks. And the legal set itself is generated once per ply and remembered, so a hundred clicks on the "
 "board cost one generation.",
 sect(src, "    boolean isAttacked(Position target, Color by)", "    private static final int[][] RAYS")),
("Support draw by threefold repetition and the fifty-move rule.",
 "twist", 8,
 "Neither is a rule about the position, so neither belongs in the engine: both are facts about the history, and both "
 "go in a wrapper. <code>DrawRules</code> takes any rule set, asks it first, and if it has not already ended the game "
 "returns DRAW when the fifty-move clock is full or the current position has now been reached three times. The clock "
 "is a counter on the board that a pawn move or a capture resets. The repetition count is a map from a position key "
 "&mdash; the pieces, the side to move, the castling rights and the en passant square, but not the clocks &mdash; to "
 "how many times it has been reached, updated inside the same critical section as the move so the count and the "
 "position can never disagree. Insufficient material stacks on top as a second wrapper that knows nothing about the "
 "first. The thresholds are constructor parameters, which is why the test is six plies long instead of a hundred "
 "moves.",
 sect(src, "class DrawRules implements RuleSet", "/** Where time comes from")),
("Castling, en passant and promotion -- the three that everybody gets wrong. Where does each live, and why there?",
 "functional", 10,
 "Castling is generated in the rules layer, not in the King, because it is the one move whose legality depends on "
 "squares being attacked and no piece can see the whole board: five conditions, the right still held, the rook still "
 "there, the squares between empty, and the king neither in check nor passing through an attacked square (landing on "
 "one is caught by the ordinary filter). Its second half is in <code>applyMove</code>, which moves the rook too. En "
 "passant lives in the Pawn, and its trick is that the victim is <i>not</i> on the square the pawn lands on, so the "
 "move records a separate capture square; the target square itself is rewritten on every single ply, because that is "
 "exactly how long the chance lives. Promotion fans out into four moves at generation time rather than one move plus "
 "an assumption, so under-promotion to a knight is offered and promoting to a king is refused by construction: it is "
 "simply not in the set.",
 sect(src, "    private void addCastles(List<Move> out)", "    /**\n     * Edit the board, and return everything")),
("Add an engine that plays the black pieces.",
 "twist", 8,
 "The move generator already exists: <code>legalMoves</code> is exactly what a search needs, so the engine only "
 "consumes the rules layer and nothing in the board or the pieces changes. An Evaluator scores a position, a Player "
 "chooses a move, and alpha-beta minimax plays a move, recurses, and takes it back &mdash; the same apply-ask-undo "
 "the legality filter already does, so the engine is fast for exactly the reason the filter is correct. The one thing "
 "worth saying out loud: the search runs on a private copy of the game made from its FEN, because playing thousands "
 "of moves on the live game would tell every spectator about moves nobody made, and would put a search's worth of "
 "work inside the game's lock.",
 X("an AI opponent", "algebraic notation")),
("Accept \"Nf3\" and \"O-O\", and give me the game as PGN afterwards.",
 "twist", 5,
 "Neither direction needs a single new rule. To read a move, print every legal move in standard notation and take the "
 "one that matches &mdash; the legal set is exactly the disambiguation oracle that notation needs, so \"Nbd2\" and "
 "\"exd5\" resolve for free. To print one, the only hard part is knowing which other legal moves would look the same, "
 "which is one filter over that same set. PGN is then a spectator that stores the moves and renders them by replaying "
 "them on a copy &mdash; it must store moves rather than text, because notation needs the position <i>before</i> each "
 "move and an observer, called after it, no longer has that. And both work on a private copy for the same reason the "
 "engine does: deciding whether a move gives check means playing it.",
 X("algebraic notation", "PGN")),
("Persist it. Now it is an online game, on two servers, and a player's phone reconnects after a tunnel.",
 "twist", 10,
 "What is stored is the starting position and the move list, not a snapshot, because replaying the moves through the "
 "same <code>play</code> that a live game uses means a resumed game cannot be in a state a played game could not "
 "reach &mdash; and the repetition counts and the fifty-move clock come back right, which a FEN alone would lose. The "
 "phone that has been away comes back holding a move it computed on a stale board, so the client sends the ply it saw "
 "and <code>play(expectedPly, move)</code> refuses it inside the same lock rather than applying it. That is the "
 "optimistic-concurrency twin of the lock, and it is the shape that survives the move to a database: "
 "<code>UPDATE games SET ... WHERE ply = ?</code>, where the row's ply is the version. Reconnecting is then just "
 "\"here is everything since ply n\", which is the move list again.",
 X("online play", "Runs every extension") + "\n" + sect(src, "    GameStatus play(int expectedPly, Move move)", "    /** The critical section itself")),
("Where does time come from, and how do you test a three-minute clock without waiting three minutes?",
 "design", 3,
 "The game has a Clock it was handed, and nothing in the engine reads the wall clock. A chess clock is then an "
 "observer, not a rule: it debits whoever just moved, adds the increment, and exposes how much each side has left. "
 "That separation is the point &mdash; a flag-fall is a result the <i>service</i> records before it accepts the next "
 "move, not a status the rules produce, which is why the same rules engine serves a bullet game and a correspondence "
 "game. And because the time is injected, the test moves two hundred seconds forward in one line and asserts the "
 "arithmetic, instead of sleeping.",
 X("the chess clock", "insufficient material")),
("Prove to me that your move generator is actually right.",
 "non-functional", 5,
 "Perft: count the leaves of the legal-move tree to a fixed depth and compare with the published numbers. From the "
 "opening position they are 20, 400, 8902 and 197281, and they are known to the unit, so a generator that reproduces "
 "them has castling, en passant, promotion, pins and check evasion right &mdash; there is no way to be accidentally "
 "correct at 197281. Three more standard positions exist precisely because they are dense in the cases that break "
 "engines, and the failure tests run those too. When a number is wrong, <code>divide</code> splits the count by first "
 "move, which tells you which move's subtree is wrong, and you recurse into it; that is how every chess engine bug "
 "has ever been found. It is also the honest speed benchmark, because all it does is generate, apply and take back.",
 X("perft", "persistence and resume")),
("Why is a Piece a class per kind and not an enum with a switch? And where would a Factory or a Builder earn its place?",
 "design", 8,
 "An enum plus a switch works right up until the two questions this system really asks. The first is check detection: "
 "<code>isAttacked</code> walks outward from the king and asks each piece it meets what it <i>can do</i> &mdash; do "
 "you ride straight lines, do you hop like a knight &mdash; so it never needs to know the list of kinds, and a piece "
 "nobody had thought of is found with no edit at all; with an enum that same line becomes a switch that every new "
 "kind must be added to, in every place that switches. The second is the Chancellor: a class is one new file and one "
 "<code>register</code> line, while an enum constant means editing the enum, the move-generation switch, the attack "
 "switch, the FEN table and the promotion list. What the enum would have bought you &mdash; a fixed set, cheap "
 "identity comparison, an <code>EnumMap</code> &mdash; you already get, because pieces hold no state and are shared, "
 "so every white rook on the board is literally the same object and <code>==</code> works. Factory earns its name the "
 "day variants ship their own piece sets from configuration: <code>Pieces.register</code> is already the registry, it "
 "just has nothing outside the code driving it yet. Builder earns nothing here: a Move has seven fields and all seven "
 "are decided by the generator in one place. (The full pattern and SOLID maps are the tables in moves 10 and 11.)",
 "// What the engine asks a piece. Never \"which kind are you?\"\n"
 "abstract class Piece {\n"
 "    boolean ridesStraight();    // rook, queen -- and a Chancellor nobody had thought of\n"
 "    boolean ridesDiagonal();    // bishop, queen\n"
 "    boolean hopsKnight();       // knight, Chancellor\n"
 "    boolean stepsOne();         // king\n"
 "    boolean attacksPawnwise();  // pawn: the one piece whose attacks are not its moves\n"
 "}\n\n"
 "// Board.isAttacked, the line that decides it: a capability question, not a kind question\n"
 "if (p.color == by) {\n"
 "    if (straight ? p.ridesStraight() : p.ridesDiagonal()) return true;\n"
 "    if (step == 1 && p.stepsOne()) return true;                       // an enemy king next door\n"
 "    if (step == 1 && !straight && p.attacksPawnwise() && d[0] == -by.forward()) return true;\n"
 "}\n\n"
 "// The enum version of the SAME line. Every new kind edits it -- and every other switch like it.\n"
 "if (p.color == by) switch (p.kind) {\n"
 "    case ROOK, QUEEN -> { if (straight) return true; }\n"
 "    case BISHOP      -> { if (!straight) return true; }\n"
 "    case KING        -> { if (step == 1) return true; }\n"
 "    case PAWN        -> { /* forward-only, so check the direction too */ }\n"
 "    // CHANCELLOR -> ... and now go and find every other switch in the file\n"
 "}\n\n"
 "// Adding a kind, the way it is here: one class, one line, and nothing else is edited\n"
 "Pieces.register('C', Chancellor::new);\n\n"
 "// Factory: not yet. The registry already exists; it earns the name when variants come from config.\n"
 "// Builder: never here. Seven fields, all decided by the generator, in one place.\n"
 "static Move enPassant(Position f, Position t, Piece moved, Piece victim, Position victimAt) { ... }\n"),
]

build(dict(
    slug="chess", title="Chess",
    subtitle="LLD &middot; Java &middot; OpenJDK 21: demo, 10 failure tests, perft to 197281 and a 50-thread race pass",
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
