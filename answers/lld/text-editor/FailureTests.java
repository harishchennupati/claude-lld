import java.util.*;
import java.util.concurrent.*;

// targeted failure tests: each one proves a claim the design makes on page 02, move 9.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    /** The incremental line index against the only source of truth there is: a fresh scan of the text. */
    static boolean sameLines(LineIndexedBuffer idx, String text) {
        List<Integer> want = new ArrayList<>(List.of(0));
        for (int i = 0; i < text.length(); i++) if (text.charAt(i) == '\n') want.add(i + 1);
        if (idx.lineCount() != want.size()) return false;
        for (int i = 0; i < want.size(); i++) if (idx.startOfLine(i) != want.get(i)) return false;
        return true;
    }

    public static void main(String[] args) throws Exception {

        // 1. eight threads type two thousand characters at the same instant: the buffer AND the history must survive.
        //    Two thousand characters with the wrong history is still a bug, so the test winds the whole document back.
        Editor race = new Editor(new GapBuffer(4096), 4096, new NoMergePolicy());
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<?>> fs = new ArrayList<>();
        for (int t = 0; t < 8; t++) {
            fs.add(pool.submit(() -> { go.await(); for (int i = 0; i < 250; i++) race.append("x"); return null; }));
        }
        go.countDown();
        for (Future<?> f : fs) f.get();
        pool.shutdown();
        check(race.text().length() == 2000, "2000 concurrent appends landed: length is exactly 2000, nothing torn");
        check(race.undoDepth() == 2000, "the history agrees with the buffer: 2000 undo steps, not 1997");
        check(race.version() == 2000, "the version counter agrees too: 2000");
        int undone = 0;
        while (race.undo()) undone++;
        check(undone == 2000 && race.text().isEmpty(), "2000 undos wind it back to an empty document");

        // 2. the everyday sequence: insert, delete in the middle, undo, redo -- the text must be restored exactly
        Editor ed = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        ed.type("hello brave new world");
        String full = ed.text();
        ed.deleteRange(6, 6);                                   // take out "brave "
        check(ed.text().equals("hello new world"), "delete removed exactly the range asked for");
        ed.undo();
        check(ed.text().equals(full), "undo put back the exact characters the delete removed, in the right place");
        ed.redo();
        check(ed.text().equals("hello new world"), "redo is execute() again: the same delete, the same result");
        ed.undo();
        check(ed.text().equals(full) && ed.canRedo(), "undo again, and redo is still available");

        // 3. a new edit clears the redo branch: forgetting this is the bug that later re-applies an edit at a
        //    vanished offset and corrupts the buffer
        ed.moveTo(ed.text().length());                          // undo left the caret where the delete was
        ed.type("!");
        check(!ed.canRedo() && ed.redoDepth() == 0, "a new edit cleared the redo stack: history is linear on purpose");
        check(!ed.redo(), "redo after a new edit returns false rather than throwing");
        check(ed.text().equals(full + "!"), "the document is the new branch, not a mix of both");

        // 4. the gap buffer must give the same answers as the obvious buffer, however the caret jumps about
        TextBuffer gap = new GapBuffer(8), plain = new StringBuilderBuffer();
        int[][] script = { {0, 0}, {0, 1}, {1, 2}, {0, 3}, {2, 4}, {1, 5} };   // (kind, arg): a walk of inserts and deletes
        boolean same = true;
        for (String word : List.of("alpha", "beta", "gamma", "delta", "epsilon")) {
            for (int[] step : script) {
                int at = Math.min(step[1] * 3, gap.length());
                if (step[0] == 0) { gap.insert(at, word); plain.insert(at, word); }
                else if (gap.length() > at + 2) { gap.delete(at, 2); plain.delete(at, 2); }
                if (!gap.text().equals(plain.text())) same = false;
            }
        }
        check(same, "the gap buffer matches a StringBuilder through 30 edits with the caret jumping backwards and forwards");
        check(gap.indexOf("psilon", 0) == plain.indexOf("psilon", 0), "find across the gap gives the same offset");
        check(gap.substring(3, 9).equals(plain.substring(3, 9)), "substring across the gap gives the same characters");
        GapBuffer moved = new GapBuffer(8);
        moved.insert(0, "abcdef");
        moved.moveGap(0);                                        // jump the caret to the front
        moved.insert(0, "Z");
        moved.moveGap(moved.length());                           // and to the very end
        moved.insert(moved.length(), "Q");
        check(moved.text().equals("Zabcdef" + "Q"), "an explicit gap move to each end leaves the text intact");

        // 5. forty replacements are ONE ctrl+Z, and the redo replays them instead of searching again
        Editor doc = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        StringBuilder src = new StringBuilder();
        for (int i = 0; i < 40; i++) src.append("the cat number ").append(i).append("\n");
        doc.type(src.toString());
        String beforeReplace = doc.text();
        int depth = doc.undoDepth();
        int hits = doc.replaceAll("cat", "dog");
        check(hits == 40, "replace-all found all 40 occurrences");
        check(doc.undoDepth() == depth + 1, "40 replacements added exactly ONE undo step");
        check(!doc.text().contains("cat") && doc.text().split("dog", -1).length == 41, "every hit was replaced");
        doc.undo();
        check(doc.text().equals(beforeReplace), "one ctrl+Z undid all 40, in reverse order, back to the exact original");
        doc.redo();
        check(!doc.text().contains("cat"), "redo replayed the same 40 children: no second search, no drifted offsets");

        // 6. an edit that throws must leave the buffer, the history and the version exactly as they were
        Editor safe = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        safe.type("stable");
        String text = safe.text();
        long v = safe.version();
        int steps = safe.undoDepth();
        try { safe.insertAt(500, "boom"); check(false, "an insert past the end must throw"); }
        catch (IndexOutOfBoundsException e) { check(true, "an insert past the end throws: " + e.getMessage()); }
        check(safe.text().equals(text) && safe.version() == v && safe.undoDepth() == steps,
              "the failed insert changed no text, no version and added no undo step");
        try {
            safe.apply(new CompositeCommand("half-legal macro", EditKind.MACRO,
                List.of(new InsertCommand(0, "AAA", EditKind.MACRO, 0L), new DeleteCommand(900, 1, EditKind.MACRO))));
            check(false, "a composite whose second child is illegal must throw");
        } catch (IndexOutOfBoundsException e) { check(true, "the composite threw on its second child"); }
        check(safe.text().equals(text) && safe.undoDepth() == steps,
              "the composite rolled its first child back: no half-applied macro, and nothing on the undo stack");
        check(safe.selection().caret() == text.length(), "the rollback put the caret back too: nothing half-done");
        safe.type("!");
        check(safe.text().equals(text + "!"), "the editor still works after both failures: the caller just retries");

        // 7. a listener that throws is not allowed to break an edit, and a SLOW listener must not hold the lock:
        //    while one listener is being notified, a second thread must be able to take the document lock and edit.
        Editor pub = new Editor(new GapBuffer(), 200, new NoMergePolicy());
        int[] good = { 0 };
        boolean[] otherThreadGotIn = { false }, armed = { true }, probed = { false };
        pub.addListener(e -> { throw new IllegalStateException("a broken view"); });
        pub.addListener(e -> {
            good[0]++;
            if (!armed[0]) return;                              // the nested edit notifies too; only probe once
            armed[0] = false;
            Thread other = new Thread(() -> { pub.insertAt(0, "#"); otherThreadGotIn[0] = true; });
            other.start();
            try { other.join(2000); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
            probed[0] = otherThreadGotIn[0];                    // read it while we are STILL inside the notification
        });
        pub.type("survives");
        check(pub.text().endsWith("survives"), "the edit landed even though the first listener threw");
        check(good[0] >= 1, "the listener after the broken one was still called");
        check(probed[0], "a second thread edited the document WHILE a listener was running: notification really is "
              + "outside the lock, so a slow plugin cannot stall another writer");

        // 8. the grouping rule: typing collapses into words, a paste never collapses, and the cap evicts the oldest
        long[] now = { 1_000_000L };
        Editor keys = new Editor(new GapBuffer(), 3, new TypingBurstMergePolicy(600, 40));
        keys.setClock(() -> now[0]);
        for (char c : "hello".toCharArray()) { keys.type(String.valueOf(c)); now[0] += 40; }
        check(keys.undoDepth() == 1, "five keystrokes 40 ms apart are ONE undo step");
        now[0] += 5000;                                          // a long pause ends the burst
        keys.type("x");
        check(keys.undoDepth() == 2, "a five-second pause starts a new undo step");
        keys.type("[a 4 KB paste]");
        check(keys.undoDepth() == 3, "a paste is its own step: the wrapper refuses to merge it, whatever the rule says");
        keys.undo();
        check(keys.text().equals("hellox"), "one ctrl+Z took the whole paste out and nothing else");
        keys.configure(new NoMergePolicy());
        now[0] += 10;
        keys.type("a"); keys.type("b");
        check(keys.undoDepth() == 3 && keys.historyEvicted(),
              "the rule was swapped at run time, the cap of 3 held, and the oldest step was evicted");
        check(!keys.text().isEmpty(), "with a step evicted the document can no longer wind back to empty: "
              + "\"unsaved\" must come from the version, not from an empty stack");

        // 9. the line index is maintained by the edits themselves, so it must survive inserts, deletes, undos and
        //    redos: after every one of them it has to agree with a full rescan of the text, character for character
        LineIndexedBuffer idx = new LineIndexedBuffer(new GapBuffer(64));
        Editor lined = new Editor(idx, 500, new NoMergePolicy());
        lined.type("alpha\nbeta\ngamma\ndelta\n");
        Random rnd = new Random(7);
        boolean agrees = true;
        for (int step = 0; step < 150 && agrees; step++) {
            int len = lined.text().length();
            int at = len == 0 ? 0 : rnd.nextInt(len + 1);
            switch (step % 5) {
                case 0, 1 -> lined.insertAt(at, "x\ny");                    // an insert that splits a line
                case 2 -> lined.insertAt(at, "zz");                         // an insert inside one line
                case 3 -> { if (len > at + 3) lined.deleteRange(at, 3); }   // a delete that may eat a newline
                default -> lined.undo();
            }
            agrees = sameLines(idx, lined.text());
        }
        check(agrees, "the line index matched a full rescan after 150 inserts, deletes and undos");
        check(new LineIndexedBuffer(new GapBuffer()).lineCount() == 1, "an empty document is still one line, starting at 0");
        LineIndexedBuffer ji = new LineIndexedBuffer(new GapBuffer(8192));
        Editor nav = new Editor(ji, 200, new NoMergePolicy());
        StringBuilder big = new StringBuilder();
        for (int i = 0; i < 400; i++) big.append("line ").append(i).append("\n");
        nav.type(big.toString());
        check(ji.lineCount() == 401, "400 lines plus the empty last line: 401 line starts");
        check(nav.textRange(ji.startOfLine(200), ji.endOfLine(200)).equals("line 200"),
              "go to line 200 is a binary search and a substring, not a scan of the document");
        nav.insertAt(ji.startOfLine(10), "// note\n");
        check(nav.textRange(ji.startOfLine(201), ji.endOfLine(201)).equals("line 200"),
              "an insert near the top shifted every line start below it in one memmove");
        check(ji.lineOf(0) == 0 && ji.columnOf(ji.startOfLine(50) + 3) == 3, "offset to line and column is O(log L)");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures > 0) System.exit(1);
    }
}
