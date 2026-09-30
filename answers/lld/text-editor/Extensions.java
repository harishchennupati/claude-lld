import java.util.*;
import java.util.concurrent.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: a piece table -- the same TextBuffer, so exactly ONE class changes when the file gets big
/**
 * A third buffer for documents a gap buffer cannot carry. The original text is never touched; everything typed is
 * appended to one growing add-buffer; the document is a list of pieces saying "take 12 characters from the original
 * at 40, then 3 from the add-buffer at 0". An insert or a delete rewrites two or three list entries and copies no
 * characters at all, so a 10 MB file edits as fast as an empty one.
 *
 * Reads here are deliberately naive (build the string, then slice it) to keep the block short. A production one
 * walks the piece list, and the Editor's snapshot becomes a lazy view over it instead of a copy per keystroke --
 * which is the second rung of the ladder on page 02, move 8. A rope is the other answer: O(log n) for reads AND
 * writes and no add-buffer growth, at the price of a tree to rebalance. Nothing outside this class changes.
 */
final class PieceTableBuffer implements TextBuffer {
    private enum Src { ORIGINAL, ADDED }
    private record Piece(Src src, int start, int len) {}
    private final String original;
    private final StringBuilder added = new StringBuilder();
    private final List<Piece> pieces = new ArrayList<>();
    private int length;

    /** Open a document over text that already exists. That string is never copied and never mutated again. */
    PieceTableBuffer(String original) {
        this.original = original == null ? "" : original;
        if (!this.original.isEmpty()) pieces.add(new Piece(Src.ORIGINAL, 0, this.original.length()));
        length = this.original.length();
    }

    public int length() { return length; }

    /** Split the piece list so an edit boundary falls between two pieces; returns the index of the piece starting at at. */
    private int splitAt(int at) {
        int off = 0;
        for (int i = 0; i < pieces.size(); i++) {
            Piece p = pieces.get(i);
            if (at == off) return i;
            if (at < off + p.len()) {
                int left = at - off;
                pieces.set(i, new Piece(p.src(), p.start(), left));
                pieces.add(i + 1, new Piece(p.src(), p.start() + left, p.len() - left));
                return i + 1;
            }
            off += p.len();
        }
        return pieces.size();
    }

    public void insert(int at, String s) {
        if (at < 0 || at > length) throw new IndexOutOfBoundsException("insert at " + at + " of " + length);
        if (s.isEmpty()) return;
        int i = splitAt(at);
        pieces.add(i, new Piece(Src.ADDED, added.length(), s.length()));
        added.append(s);                                   // append-only: nothing already written ever moves
        length += s.length();
    }

    public String delete(int at, int len) {
        if (at < 0 || len < 0 || at + len > length) throw new IndexOutOfBoundsException("delete " + len + " at " + at + " of " + length);
        String gone = substring(at, at + len);
        int i = splitAt(at), j = splitAt(at + len);
        pieces.subList(i, j).clear();                      // a delete is dropping list entries, not moving characters
        length -= len;
        return gone;
    }

    public String text() {
        StringBuilder sb = new StringBuilder(length);
        for (Piece p : pieces) {
            CharSequence from = p.src() == Src.ORIGINAL ? original : added;
            sb.append(from, p.start(), p.start() + p.len());
        }
        return sb.toString();
    }
    public String substring(int from, int to) { return text().substring(from, to); }
    public int indexOf(String needle, int from) { return text().indexOf(needle, from); }
    /** How many pieces the document is currently made of: the real memory cost of this buffer. */
    int pieceCount() { return pieces.size(); }
}

// ---- ext: lines -- "go to line 4000" and "draw lines 200 to 250" without scanning the document
/**
 * Where every line starts, kept up to date by the edits themselves. It wraps ANY TextBuffer instead of changing one,
 * so the Editor, the commands and the lock do not know it exists -- the same Decorator seam as PasteIsItsOwnStep,
 * this time around the storage. Because undo and redo also go through insert() and delete(), the index follows them
 * for free; there is no second code path to keep in step.
 *
 * starts[i] is the offset of the first character of line i, and starts[0] is always 0, so an empty document has one
 * line. A lookup is a binary search: O(log L). An edit shifts every start below it by one System.arraycopy: on a
 * 40,000-line file that is a 160 KB memmove, about 10 us, which is why this is the right answer up to roughly a
 * million lines. Past that the line counts belong inside the buffer's own pieces -- a piece table or a rope carrying
 * a newline count per node -- and the shift becomes O(log n).
 */
final class LineIndexedBuffer implements TextBuffer {
    private final TextBuffer base;
    private int[] starts = new int[16];
    private int n = 1;                                     // starts[0] = 0: an empty document is one empty line

    /** Wrap any storage. Nothing above it changes: it is still a TextBuffer. */
    LineIndexedBuffer(TextBuffer base) {
        this.base = Objects.requireNonNull(base);
        String t = base.text();                            // one scan, once, when the file is opened
        for (int i = 0; i < t.length(); i++) if (t.charAt(i) == '\n') add(i + 1);
    }
    private void add(int off) { grow(n + 1); starts[n++] = off; }
    private void grow(int need) { if (need > starts.length) starts = Arrays.copyOf(starts, Math.max(need, starts.length * 2)); }
    /** The index of the first line that starts strictly after off. */
    private int upper(int off) {
        int lo = 0, hi = n;
        while (lo < hi) { int mid = (lo + hi) >>> 1; if (starts[mid] <= off) lo = mid + 1; else hi = mid; }
        return lo;
    }

    public void insert(int at, String s) {
        base.insert(at, s);
        int add = 0;
        for (int i = 0; i < s.length(); i++) if (s.charAt(i) == '\n') add++;
        int i = upper(at);
        grow(n + add);
        System.arraycopy(starts, i, starts, i + add, n - i);            // one memmove: everything below the edit
        for (int k = i + add; k < n + add; k++) starts[k] += s.length();
        int w = i;
        for (int c = 0; c < s.length(); c++) if (s.charAt(c) == '\n') starts[w++] = at + c + 1;
        n += add;
    }

    public String delete(int at, int len) {
        String gone = base.delete(at, len);
        int i = upper(at), j = upper(at + len);                          // lines that began inside the deleted range
        System.arraycopy(starts, j, starts, i, n - j);
        n -= (j - i);
        for (int k = i; k < n; k++) starts[k] -= len;
        return gone;
    }

    /** How many lines the document has. An empty document has one. */
    int lineCount() { return n; }
    /** The offset the given line starts at. Line numbers are zero-based here; a UI adds one. */
    int startOfLine(int line) { return starts[Math.max(0, Math.min(line, n - 1))]; }
    /** One past the last character of the line, not counting its newline. */
    int endOfLine(int line) { return line + 1 < n ? starts[line + 1] - 1 : length(); }
    /** Which line an offset falls on: one binary search, no scan. */
    int lineOf(int offset) { return Math.max(0, upper(offset) - 1); }
    /** Line and column of an offset, which is what a status bar shows. */
    int columnOf(int offset) { return offset - startOfLine(lineOf(offset)); }

    public int length() { return base.length(); }
    public String text() { return base.text(); }
    public String substring(int from, int to) { return base.substring(from, to); }
    public int indexOf(String needle, int from) { return base.indexOf(needle, from); }
}

// ---- ext: rich text -- "bold this selection" is an edit too, and styles are a Flyweight
/**
 * One character style. Interned, so a million bold characters share ONE Style object and the table holds references
 * rather than copies: Flyweight, and it arrives because rich text demanded it, not because it was on a list.
 */
record Style(boolean bold, boolean italic, String colour) {
    private static final Map<String, Style> POOL = new ConcurrentHashMap<>();
    /** The shared instance for this combination; the same arguments always give back the same object. */
    static Style of(boolean bold, boolean italic, String colour) {
        return POOL.computeIfAbsent(bold + "/" + italic + "/" + colour, k -> new Style(bold, italic, colour));
    }
    /** How many distinct styles exist in the whole process. */
    static int pooled() { return POOL.size(); }
}

/** A stretch of characters carrying one style. The text itself stays plain; styles ride alongside it. */
record StyleRun(int from, int to, Style style) {}

/** The styles of one document. Kept beside the buffer, so a plain-text editor pays nothing for it. */
final class StyleTable {
    private List<StyleRun> runs = new ArrayList<>();
    /** An immutable view of the runs, newest last. */
    List<StyleRun> runs() { return List.copyOf(runs); }
    /** Replace the whole run list. Used by undo, which restores the list it saved. */
    void set(List<StyleRun> newRuns) { runs = new ArrayList<>(newRuns); }
    /** Add one run. */
    void add(StyleRun r) { runs.add(r); }
}

/**
 * Bold, italic or a colour over a range, as an ordinary EditCommand: it goes through apply(), lands on the undo
 * stack, and one ctrl+Z takes the bold off again. Its memento is the run list as it was -- small, because runs are
 * ranges, not characters. It reports MACRO rather than TYPING so the merge wrapper will never fold it into a word.
 */
final class StyleCommand implements EditCommand {
    private final StyleTable table;
    private final StyleRun run;
    private List<StyleRun> before;
    /** Apply style to [from, to) of this table. */
    StyleCommand(StyleTable table, int from, int to, Style style) { this.table = table; this.run = new StyleRun(from, to, style); }
    public void execute(Document doc) { before = table.runs(); table.add(run); }
    public void undo(Document doc) { table.set(before); }
    public String label() { return "style"; }
    public EditKind kind() { return EditKind.MACRO; }
}

// ---- ext: a macro -- an arbitrary run of edits as one ctrl+Z
/**
 * Begin and end, around anything you like: the edits are buffered instead of applied, and commit() hands the Editor
 * one CompositeCommand. ReplaceAllCommand is this same shape with the children found by a search instead of by a
 * caller, which is why adding macros needed no new machinery in the Editor, the history or the lock.
 */
final class Macro {
    private final Editor editor;
    private final String label;
    private final List<EditCommand> parts = new ArrayList<>();
    /** Start recording. Nothing touches the document until commit(). */
    Macro(Editor editor, String label) { this.editor = editor; this.label = label; }
    /** Record an insert. */
    Macro insert(int at, String s) { parts.add(new InsertCommand(at, s, EditKind.MACRO, 0L)); return this; }
    /** Record a delete. */
    Macro delete(int at, int len) { parts.add(new DeleteCommand(at, len, EditKind.MACRO)); return this; }
    /** Apply the whole run as ONE undo step. If any child throws, the ones already applied are rolled back. */
    long commit() { return editor.apply(new CompositeCommand(label, EditKind.MACRO, parts)); }
}

// ---- ext: undo puts the caret back -- one decorator, and no command had to learn about it
/**
 * Undo that restores the selection, not just the text. Wraps any command: it notes where the caret and the highlight
 * were before execute, and puts them back after undo. One class, one line at the call site, and InsertCommand,
 * DeleteCommand and every composite are untouched -- the same Decorator seam PasteIsItsOwnStep uses.
 */
final class RestoresSelection implements EditCommand {
    private final EditCommand base;
    private Selection before;
    /** Wrap a command so its undo also restores the pre-edit selection. */
    RestoresSelection(EditCommand base) { this.base = Objects.requireNonNull(base); }
    public void execute(Document doc) { before = doc.selection(); base.execute(doc); }
    public void undo(Document doc) { base.undo(doc); if (before != null) doc.select(before.anchor(), before.caret()); }
    public String label() { return base.label(); }
    public EditKind kind() { return base.kind(); }
}

// ---- ext: persistence -- a journal of commands, and replay rebuilds text AND history
/** Where the journal goes. A file, a socket, a table: the editor never learns which. */
interface Journal {
    /** Append one line. Called after the unlock, so a slow disk never blocks a typist. */
    void append(String line);
    /** Every line ever appended, oldest first. */
    List<String> readAll();
}

/** A journal in memory, which is all a test needs. A real one is the same class over a file channel. */
final class MemoryJournal implements Journal {
    private final List<String> lines = new ArrayList<>();
    public synchronized void append(String line) { lines.add(line); }
    public synchronized List<String> readAll() { return List.copyOf(lines); }
}

/**
 * The only place that knows a command's wire format. Commands were already data -- that is why persistence is a
 * codec and a replay loop rather than a redesign. An insert writes its offset and its text; a delete writes its
 * offset and its length (the characters come back from the document on replay); a composite writes its child count.
 */
final class CommandCodec {
    private CommandCodec() { }
    /** One command as one or more lines, parents before children. */
    static List<String> encode(EditCommand c) {
        List<String> out = new ArrayList<>();
        if (c instanceof InsertCommand i) out.add("I\t" + i.at() + "\t" + i.kind() + "\t" + esc(i.text()));
        else if (c instanceof DeleteCommand d) out.add("D\t" + d.at() + "\t" + d.len() + "\t" + d.kind());
        else if (c instanceof CompositeCommand k) {
            List<EditCommand> kids = k.children();
            out.add("C\t" + esc(k.label()) + "\t" + kids.size());
            for (EditCommand kid : kids) out.addAll(encode(kid));
        } else throw new IllegalArgumentException("no codec for " + c.getClass().getSimpleName());
        return out;
    }
    /** Read one command (and its children) starting at cursor[0], advancing the cursor past what it consumed. */
    static EditCommand decode(List<String> lines, int[] cursor) {
        String[] f = lines.get(cursor[0]++).split("\t", -1);
        switch (f[0]) {
            case "I": return new InsertCommand(Integer.parseInt(f[1]), unesc(f[3]), EditKind.valueOf(f[2]), 0L);
            case "D": return new DeleteCommand(Integer.parseInt(f[1]), Integer.parseInt(f[2]), EditKind.valueOf(f[3]));
            case "C": {
                int n = Integer.parseInt(f[2]);
                List<EditCommand> kids = new ArrayList<>();
                for (int i = 0; i < n; i++) kids.add(decode(lines, cursor));
                return new CompositeCommand(unesc(f[1]), EditKind.MACRO, kids);
            }
            default: throw new IllegalArgumentException("bad journal line: " + String.join("\\t", f));
        }
    }
    private static String esc(String s) { return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n"); }
    private static String unesc(String s) { return s.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\"); }
}

/**
 * Writes every landed change to the journal. It is an ordinary listener, so it runs AFTER the unlock: a slow disk
 * never blocks the typist, and the price of that is an honest one -- if the process dies in the microsecond between
 * the unlock and the append, the last edit is lost. Moving the append inside the lock buys durability and costs
 * milliseconds per keystroke, which is why real editors do exactly this and autosave on top.
 */
final class JournalListener implements EditListener {
    private final Journal journal;
    /** Write to this journal. */
    JournalListener(Journal journal) { this.journal = journal; }
    public void onEdit(EditEvent e) {
        switch (e.kind()) {
            case "edit" -> CommandCodec.encode(e.command()).forEach(journal::append);
            case "undo" -> journal.append("U");
            case "redo" -> journal.append("R");
            default -> { }
        }
    }
    /** Rebuild an editor from a journal: the text comes back, and so does the undo stack, because the log IS the history. */
    static Editor replay(Journal journal) {
        Editor ed = new Editor(new GapBuffer(), 4096, new NoMergePolicy());
        List<String> lines = journal.readAll();
        int[] cursor = { 0 };
        while (cursor[0] < lines.size()) {
            String head = lines.get(cursor[0]);
            if (head.equals("U")) { cursor[0]++; ed.undo(); }
            else if (head.equals("R")) { cursor[0]++; ed.redo(); }
            else ed.apply(CommandCodec.decode(lines, cursor));
        }
        return ed;
    }
}

// ---- ext: two people at once -- why a stack cannot do it, and the one function OT adds
/**
 * A stack can undo MY last step. It cannot undo my last step while keeping yours, because your edit moved my
 * offsets: my "delete 3 characters at 40" now means different characters. Two families fix it, and neither is a
 * lock. Operational transformation keeps a per-site log and rebases every incoming operation against the ones it
 * did not see -- for two inserts that whole idea is the function below. A CRDT gives every character a unique,
 * totally ordered id instead of an offset, so there is nothing to rebase, at the cost of carrying those ids
 * forever. In both, undo stops meaning "pop" and starts meaning "emit the transformed inverse of my own operation".
 */
final class Ot {
    private Ot() { }
    /** My insert at mine, rebased over a concurrent insert of theirLen characters at theirs. siteWins breaks the tie. */
    static int insertOverInsert(int mine, int theirs, int theirLen, boolean siteWins) {
        if (mine < theirs || (mine == theirs && siteWins)) return mine;
        return mine + theirLen;
    }
    /** My insert at mine, rebased over a concurrent delete of theirLen characters at theirs. */
    static int insertOverDelete(int mine, int theirs, int theirLen) {
        if (mine <= theirs) return mine;
        return mine >= theirs + theirLen ? mine - theirLen : theirs;     // inside the deleted range: collapse to its start
    }
}

// ---- ext: incremental syntax highlighting -- retokenise the lines the edit touched, not the file
/**
 * The version number in the event is what makes this cheap. On every edit it compares the new text with the text it
 * last saw, finds the first and last line that differ, and re-tokenises only those. One keystroke in a thousand-line
 * file re-tokenises one line; a paste of forty lines re-tokenises forty. It never takes the editor's lock, because
 * the event already carries an immutable snapshot.
 */
final class Highlighter implements EditListener {
    private static final Set<String> KEYWORDS = Set.of("class", "void", "int", "return", "if", "else", "new", "final");
    private List<String> lines = List.of("");
    private int retokenised, keywordsFound;

    public void onEdit(EditEvent e) {
        List<String> now = List.of(e.text().split("\n", -1));
        int lo = 0;
        while (lo < lines.size() && lo < now.size() && lines.get(lo).equals(now.get(lo))) lo++;
        int hi = 0;
        while (hi < lines.size() - lo && hi < now.size() - lo
               && lines.get(lines.size() - 1 - hi).equals(now.get(now.size() - 1 - hi))) hi++;
        for (int i = lo; i < now.size() - hi; i++) { tokenise(now.get(i)); retokenised++; }
        lines = now;
    }
    private void tokenise(String line) { for (String w : line.split("\\W+")) if (KEYWORDS.contains(w)) keywordsFound++; }
    /** How many lines have been re-tokenised in total; compare it with edits x lines to see what incremental bought. */
    int retokenised() { return retokenised; }
    /** How many lines the document currently has. */
    int lineCount() { return lines.size(); }
}

// ---- ext: plugins -- a listener somebody else wrote, and what happens when it throws
/** A plugin is a listener with a name, installed by a user rather than by the editor. */
interface Plugin {
    /** How the plugin appears in the disabled list. */
    String name();
    /** Called with every edit, after the unlock. It is allowed to throw; that is the point of the host. */
    void onEdit(EditEvent e);
}

/**
 * One listener that fans out to every installed plugin. The Editor already swallows an exception from a listener, so
 * typing is safe; the host adds the part a product needs -- a plugin that throws is counted, and after three strikes
 * it is unsubscribed and named, instead of being caught silently forever.
 */
final class PluginHost implements EditListener {
    private final Map<String, Plugin> live = new LinkedHashMap<>();
    private final Map<String, Integer> strikes = new HashMap<>();
    private final List<String> disabled = new ArrayList<>();
    /** Install a plugin. It starts receiving the next edit. */
    void install(Plugin p) { live.put(p.name(), p); }
    public void onEdit(EditEvent e) {
        for (Plugin p : new ArrayList<>(live.values())) {
            try { p.onEdit(e); }
            catch (RuntimeException ex) {
                if (strikes.merge(p.name(), 1, Integer::sum) >= 3) { live.remove(p.name()); disabled.add(p.name()); }
            }
        }
    }
    /** The plugins still receiving events. */
    Set<String> installed() { return live.keySet(); }
    /** The plugins that were switched off for throwing three times. */
    List<String> disabled() { return List.copyOf(disabled); }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) {
        // a piece table behind the same interface: the Editor does not change a line
        Editor big = new Editor(new PieceTableBuffer("the quick brown fox jumps over the lazy dog"), 200, new NoMergePolicy());
        big.insertAt(4, "very ");
        big.deleteRange(0, 4);
        System.out.println("piece table:  \"" + big.text() + "\"");
        big.undo(); big.undo();
        System.out.println("  two undos:  \"" + big.text() + "\"  (same commands, different storage)");

        // lines: go to line 200 of a 500-line file, and draw three lines, without scanning the document
        LineIndexedBuffer lines = new LineIndexedBuffer(new GapBuffer(40000));
        Editor src = new Editor(lines, 200, new NoMergePolicy());
        StringBuilder body = new StringBuilder();
        for (int i = 0; i < 500; i++) body.append("line ").append(i).append("\n");
        src.type(body.toString());
        src.insertAt(lines.startOfLine(200), "// inserted at the top of line 200\n");   // every start below it shifts
        System.out.println("lines:        " + lines.lineCount() + " lines; line 201 starts at " + lines.startOfLine(201)
            + ", offset 1000 is line " + lines.lineOf(1000) + " column " + lines.columnOf(1000));
        System.out.println("  viewport:   \"" + src.textRange(lines.startOfLine(200), lines.endOfLine(202)).replace("\n", " | ") + "\"");
        src.undo();
        System.out.println("  after undo: " + lines.lineCount() + " lines again (undo goes through insert/delete too)");

        // rich text: bold is a command, and the styles are shared objects
        Editor rich = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        StyleTable styles = new StyleTable();
        rich.type("bold me please");
        rich.apply(new StyleCommand(styles, 0, 4, Style.of(true, false, "#000")));
        rich.apply(new StyleCommand(styles, 5, 7, Style.of(true, false, "#000")));   // the SAME Style instance
        System.out.println("rich text:    runs=" + styles.runs().size() + "  distinct Style objects pooled=" + Style.pooled()
            + "  same instance reused=" + (Style.of(true, false, "#000") == Style.of(true, false, "#000")));
        rich.undo();
        System.out.println("  one ctrl+Z: runs=" + styles.runs().size() + "  (a style change undoes like any edit)");

        // a macro: three edits, one undo step
        Editor mac = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        mac.type("one two three");
        int before = mac.undoDepth();
        new Macro(mac, "tidy up").delete(0, 4).insert(0, "1 ").insert(2, "[").commit();
        System.out.println("macro:        \"" + mac.text() + "\"  steps added=" + (mac.undoDepth() - before));
        mac.undo();
        System.out.println("  one ctrl+Z: \"" + mac.text() + "\"  three edits came out together");

        // undo that puts the caret back
        Editor car = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        car.type("abcdef");
        car.moveTo(2);
        Selection was = car.selection();
        car.apply(new RestoresSelection(new InsertCommand(2, "XYZ", EditKind.PASTE, 0L)));
        System.out.println("caret:        after paste caret=" + car.selection().caret() + ", was " + was.caret());
        car.undo();
        System.out.println("  after undo: caret=" + car.selection().caret() + "  (the decorator put it back)");

        // persistence: a journal of commands, replayed into a fresh editor
        MemoryJournal log = new MemoryJournal();
        Editor live = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        live.addListener(new JournalListener(log));
        live.type("the cat sat");
        live.replaceAll("cat", "dog");
        live.undo();
        live.redo();
        Editor rebuilt = JournalListener.replay(log);
        System.out.println("journal:      " + log.readAll().size() + " lines -> replayed \"" + rebuilt.text()
            + "\"  matches=" + rebuilt.text().equals(live.text()) + "  undo steps=" + rebuilt.undoDepth());

        // two people at once: the transform, not a lock
        System.out.println("OT:           my insert at 40, yours of 5 chars at 10 -> mine becomes "
            + Ot.insertOverInsert(40, 10, 5, false) + "; your delete of 5 at 10 -> mine becomes "
            + Ot.insertOverDelete(40, 10, 5));

        // incremental highlighting: one keystroke does not re-read the file
        Editor code = new Editor(new GapBuffer(), 4096, new NoMergePolicy());
        Highlighter hl = new Highlighter();
        code.addListener(hl);
        StringBuilder file = new StringBuilder();
        for (int i = 0; i < 200; i++) file.append("int x").append(i).append(" = ").append(i).append(";\n");
        code.type(file.toString());
        int afterLoad = hl.retokenised();
        for (int i = 0; i < 10; i++) code.type("z");
        System.out.println("highlighter:  " + hl.lineCount() + " lines; loading cost " + afterLoad
            + " line tokenisations, then ten keystrokes cost " + (hl.retokenised() - afterLoad)
            + " lines, not " + (10 * hl.lineCount()));

        // plugins: three strikes and it is out
        Editor host = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        PluginHost plugins = new PluginHost();
        int[] seen = { 0 };
        plugins.install(new Plugin() {
            public String name() { return "word-count"; }
            public void onEdit(EditEvent e) { seen[0]++; }
        });
        plugins.install(new Plugin() {
            public String name() { return "broken-linter"; }
            public void onEdit(EditEvent e) { throw new IllegalStateException("npe in a plugin"); }
        });
        host.addListener(plugins);
        for (int i = 0; i < 5; i++) host.type("a");
        System.out.println("plugins:      text=\"" + host.text() + "\" (typing never noticed), word-count saw " + seen[0]
            + " edits, disabled=" + plugins.disabled());
    }
}
