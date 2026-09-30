import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Targeted failure tests: 1-12 prove the claims this design makes on page 02, move 9; 13-20 prove the claims the
// follow-ups make on page 05. Nothing here is a demo; every line either passes or the file exits non-zero.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) { System.out.println((ok ? "PASS " : "FAIL ") + what); if (!ok) failures++; }

    public static void main(String[] args) throws Exception {

        // 1. mkdir -p creates every missing level, is safe to repeat, and refuses to hang a directory off a file
        FileSystem fs = new FileSystem();
        fs.mkdirs("/a/b/c/d");
        check(fs.exists("/a") && fs.exists("/a/b/c") && fs.exists("/a/b/c/d"), "mkdir -p created every missing level");
        fs.mkdirs("/a/b");
        check(fs.ls("/a").equals(List.of("b")), "mkdir -p on a directory that exists changes nothing");
        fs.putFile("/a/file.txt", "bytes");
        try { fs.mkdirs("/a/file.txt/deeper"); check(false, "a directory under a file must be refused"); }
        catch (NotADirectoryException e) { check(true, "a directory under a file is refused: " + e.getMessage()); }
        try { fs.mkdirs("/a/file.txt"); check(false, "mkdir -p on an existing file must be refused"); }
        catch (AlreadyExistsException e) { check(true, "mkdir -p on an existing file says it already exists: " + e.getMessage()); }
        catch (FsException e) { check(false, "mkdir -p on an existing file must say it already exists, not: " + e.getMessage()); }

        // 2. the path is normalised once: "." disappears, ".." pops, and ".." above the root clamps at the root
        check(FsPath.of("/a/./b/../b/c").toString().equals("/a/b/c"), "\".\" and \"..\" resolve to one canonical path");
        check(FsPath.of("/a/../../../..").toString().equals("/"), "\"..\" above the root clamps at the root, it does not escape");
        fs.mkdirs("/home/harish/notes");
        fs.putFile("/home/harish/notes/todo.txt", "buy milk");
        check(fs.readString("/home/harish/notes/../notes/./todo.txt").equals("buy milk"), "a path with .. reads the same file");

        // 3. moving a directory into its own subtree would orphan it, so it is refused and nothing moves
        fs.mkdirs("/src/deep/deeper");
        List<String> before3 = fs.find("/src", NodeFilter.ANY);
        try { fs.move("/src", "/src/deep/copy"); check(false, "a move into its own subtree must be refused"); }
        catch (InvalidMoveException e) { check(true, "a move into its own subtree is refused: " + e.getMessage()); }
        check(fs.find("/src", NodeFilter.ANY).equals(before3), "and the tree is exactly as it was");
        try { fs.move("/nope", "/nope"); check(false, "moving a missing path onto itself must say not found"); }
        catch (NotFoundException e) { check(true, "moving a missing path onto itself is 'not found', not a silent success"); }

        // 4. rm on a non-empty directory is loud, and recursive takes the whole subtree with it
        long bytesBefore4 = fs.totalBytes(), filesBefore4 = fs.fileCount();
        try { fs.delete("/home/harish", false); check(false, "rm on a non-empty directory must be refused"); }
        catch (DirectoryNotEmptyException e) { check(true, "rm on a non-empty directory is refused: " + e.getMessage()); }
        check(fs.totalBytes() == bytesBefore4 && fs.fileCount() == filesBefore4, "and nothing was freed by the refused rm");
        fs.delete("/home/harish", true);
        check(!fs.exists("/home/harish/notes/todo.txt") && fs.fileCount() == filesBefore4 - 1,
              "recursive rm took the subtree and the accounting with it");

        // 5. a write over quota is refused before any byte moves: old bytes, counters and the tree are untouched
        FileSystem q = new FileSystem();
        AuditGuard audit = new AuditGuard(WriteGuard.allOf(new CapacityGuard(64, 1024)));
        q.configure(audit);
        q.putFile("/keep.txt", "small");
        long bytes5 = q.totalBytes(), files5 = q.fileCount();
        try { q.putFile("/toobig.bin", "z".repeat(200)); check(false, "a file over the per-file cap must be refused"); }
        catch (QuotaExceededException e) { check(true, "a file over the per-file cap is refused: " + e.getMessage()); }
        check(q.totalBytes() == bytes5 && q.fileCount() == files5 && !q.exists("/toobig.bin"),
              "the refused create left no file, no bytes and no reservation behind");
        try { q.append("/keep.txt", "z".repeat(100)); check(false, "an append over the cap must be refused"); }
        catch (QuotaExceededException e) { check(true, "an append over the per-file cap is refused"); }
        check(q.readString("/keep.txt").equals("small") && q.totalBytes() == bytes5,
              "the refused append left the old bytes and the counter exactly as they were");
        check(audit.refused().size() == 2, "the decorating guard recorded both refusals without either rule knowing");

        // 5b. a second rule stacks on the first: neither knows the other exists and FileSystem was never opened
        q.mkdirs("/etc");
        q.putFile("/etc/passwd", "root:x:0");
        q.configure(WriteGuard.allOf(new CapacityGuard(64, 1024), new ReadOnlySubtreeGuard("/etc")));
        try { q.append("/etc/passwd", "!"); check(false, "a write under a read-only subtree must be refused"); }
        catch (FsException e) { check(true, "a write under a read-only subtree is refused: " + e.getMessage()); }
        q.append("/keep.txt", "!");
        check(q.readString("/etc/passwd").equals("root:x:0") && q.readString("/keep.txt").equals("small!"),
              "the read-only subtree kept its bytes and the same two rules still allowed the write next door");
        int refused5 = 0;
        for (Runnable change : List.<Runnable>of(() -> q.delete("/etc/passwd", false), () -> q.move("/etc/passwd", "/passwd"),
                                                 () -> q.mkdirs("/etc/cron.d"), () -> q.delete("/etc", true)))
            try { change.run(); } catch (FsException e) { refused5++; }
        check(refused5 == 4 && q.readString("/etc/passwd").equals("root:x:0") && !q.exists("/etc/cron.d"),
              "read-only means rm, mv and mkdir under /etc are refused too, not only byte writes");
        FileSystem ssl = new FileSystem();
        ssl.mkdirs("/etc/ssl");
        ssl.configure(new ReadOnlySubtreeGuard("/etc/ssl"));
        try { ssl.delete("/etc", true); check(false, "rm -r of a folder above a read-only one must be refused"); }
        catch (FsException e) { check(ssl.exists("/etc/ssl"), "and rm -r of a folder ABOVE a read-only one is refused, because it would take it along"); }

        // 6. eight threads appending to ONE file lose nothing, and the running total still matches a fresh walk
        FileSystem race = new FileSystem();
        race.putFile("/log.txt", "");
        CountDownLatch go6 = new CountDownLatch(1);
        ExecutorService pool6 = Executors.newFixedThreadPool(8);
        List<Future<?>> jobs6 = new ArrayList<>();
        for (int t = 0; t < 8; t++)
            jobs6.add(pool6.submit(() -> { go6.await(); for (int i = 0; i < 500; i++) race.append("/log.txt", "x"); return null; }));
        go6.countDown();
        for (Future<?> f : jobs6) f.get();
        pool6.shutdown();
        check(race.read("/log.txt").length == 4000, "8 threads x 500 appends left exactly 4000 bytes: no lost update");
        check(race.totalBytes() == race.du("/"), "the incremental byte count still equals a fresh du of the tree");

        // 7. fifty threads creating files in ONE directory: all fifty are there, and one name is one entry
        FileSystem burst = new FileSystem();
        burst.mkdirs("/inbox");
        CountDownLatch go7 = new CountDownLatch(1);
        ExecutorService pool7 = Executors.newFixedThreadPool(16);
        List<Future<?>> jobs7 = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final int n = i;
            jobs7.add(pool7.submit(() -> { go7.await(); burst.putFile("/inbox/m" + n + ".txt", "body " + n); return null; }));
        }
        go7.countDown();
        for (Future<?> f : jobs7) f.get();
        check(burst.ls("/inbox").size() == 50 && burst.fileCount() == 50, "50 concurrent creates produced exactly 50 files");
        check(new TreeSet<>(burst.ls("/inbox")).size() == 50, "and fifty distinct names, in sorted order");
        CountDownLatch go7b = new CountDownLatch(1);
        List<Future<?>> dup = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            final String body = "writer" + i;
            dup.add(pool7.submit(() -> { go7b.await(); burst.putFile("/inbox/same.txt", body); return null; }));
        }
        go7b.countDown();
        for (Future<?> f : dup) f.get();
        pool7.shutdown();
        check(burst.ls("/inbox").size() == 51 && burst.fileCount() == 51,
              "two threads racing one name left one entry and counted the file once");
        check(burst.readString("/inbox/same.txt").startsWith("writer"), "and the winner's bytes are whole, not interleaved");

        // 8. watchers run AFTER the unlock: another thread can write while a watcher is still busy
        FileSystem w = new FileSystem();
        w.mkdirs("/w");
        CountDownLatch release = new CountDownLatch(1);
        AtomicBoolean secondFinished = new AtomicBoolean(false);
        w.watch("/w", e -> {
            if (!e.path().endsWith("first.txt")) return;
            try { release.await(3, TimeUnit.SECONDS); } catch (InterruptedException ignored) { }
        });
        Thread a = new Thread(() -> w.putFile("/w/first.txt", "a"));
        a.start();
        Thread.sleep(150);                                                  // a is now inside its slow watcher
        Thread b = new Thread(() -> { w.putFile("/w/second.txt", "b"); secondFinished.set(true); release.countDown(); });
        b.start();
        b.join(2000);
        check(secondFinished.get(), "a second writer got through while a watcher was still running: the lock was already released");
        a.join(3000);
        w.watch("/w", e -> { throw new IllegalStateException("this watcher is broken"); });
        w.putFile("/w/third.txt", "c");
        check(w.readString("/w/third.txt").equals("c"), "a watcher that throws cannot fail the write that told it");

        // 9. deleting a file somebody is reading unlinks the name; the bytes live until that reader closes
        FileSystem h = new FileSystem();
        h.putFile("/open.txt", "still readable");
        Handle handle = h.open("/open.txt");
        h.delete("/open.txt", false);
        check(!h.exists("/open.txt") && handle.readString().equals("still readable"),
              "the name is gone and the open reader still gets its bytes");
        check(handle.state() == FileState.UNLINKED, "the file is UNLINKED, not yet freed");
        handle.close();
        check(handle.state() == FileState.FREED && h.totalBytes() == 0, "closing the last handle freed the bytes");

        // 10. a rename and a write at the same instant: no byte is lost, and the two locks cannot deadlock
        FileSystem mv = new FileSystem();
        mv.mkdirs("/a/b");
        mv.putFile("/a/b/f.txt", "");
        AtomicInteger landed = new AtomicInteger();
        AtomicBoolean stop = new AtomicBoolean(false);
        CountDownLatch go10 = new CountDownLatch(1);
        ExecutorService pool10 = Executors.newFixedThreadPool(5);
        List<Future<?>> writers10 = new ArrayList<>();
        for (int t = 0; t < 4; t++)
            writers10.add(pool10.submit(() -> {
                go10.await();
                for (int i = 0; i < 500; i++) {
                    try { mv.append("/a/b/f.txt", "x"); landed.incrementAndGet(); }
                    catch (NotFoundException e) { i--; }                 // the directory is called b2 this instant: retry
                }
                return null;
            }));
        Future<?> renamer = pool10.submit(() -> {
            go10.await();
            while (!stop.get()) { mv.move("/a/b", "/a/b2"); mv.move("/a/b2", "/a/b"); Thread.yield(); }
            return null;
        });
        go10.countDown();
        for (Future<?> f : writers10) f.get(30, TimeUnit.SECONDS);       // a deadlock here times out and fails the run
        stop.set(true);
        renamer.get(30, TimeUnit.SECONDS);
        pool10.shutdown();
        check(landed.get() == 2000 && mv.read("/a/b/f.txt").length == 2000,
              "2000 appends survived a directory being renamed under them, with nothing lost and nothing torn");
        check(mv.totalBytes() == mv.du("/"), "and the byte accounting still matches a fresh walk after the renames");

        // 11. a slow subscriber must not slow the file system down, and a full queue drops instead of blocking
        FileSystem idx = new FileSystem();
        idx.mkdirs("/idx");
        CountDownLatch blocked = new CountDownLatch(1);
        AsyncWatcher async = new AsyncWatcher(4, e -> { try { blocked.await(3, TimeUnit.SECONDS); } catch (InterruptedException ignored) { } });
        idx.watch("/idx", async);
        long startMs = System.currentTimeMillis();
        for (int i = 0; i < 200; i++) idx.putFile("/idx/f" + i + ".txt", "x");
        long tookMs = System.currentTimeMillis() - startMs;
        check(tookMs < 1000, "200 writes finished in " + tookMs + " ms while the subscriber was blocked: a watcher never holds up a write");
        check(async.dropped() > 0, "a full queue dropped " + async.dropped() + " events rather than block the writer or grow without limit");
        blocked.countDown();
        async.close();
        check(idx.fileCount() == 200, "and every write landed anyway: a dropped notification is never a lost file");

        // 12. a watcher hears what leaves its folder: a file moved out of it, and the delete of a folder above it
        FileSystem ws = new FileSystem();
        ws.mkdirs("/var/log");
        ws.mkdirs("/tmp");
        ws.putFile("/var/log/app.log", "x");
        List<FsEvent> heard = new CopyOnWriteArrayList<>();
        ws.watch("/var/log", heard::add);
        ws.move("/var/log/app.log", "/tmp/app.log");
        check(heard.size() == 1 && "/var/log/app.log".equals(heard.get(0).from()),
              "a watcher on /var/log hears a file moved OUT of it, and the event carries the old path");
        ws.delete("/var", true);
        check(heard.size() == 2 && heard.get(1).kind() == EventKind.DELETED,
              "and it hears /var being deleted, which took /var/log with it");

        // 13. a refused call never reaches the journal, so a replay rebuilds exactly the live tree
        Journal journal = new InMemoryJournal();
        FileSystem live = new FileSystem();
        JournaledFs jfs = new JournaledFs(live, journal);
        jfs.mkdirs("/var/log");
        jfs.putFile("/var/log/app.log", "started");
        live.configure(new CapacityGuard(16, 1024));
        try { jfs.append("/var/log/app.log", " and a line that is far too long"); } catch (QuotaExceededException expected) { }
        try { jfs.append("/var/log/missing.log", "x"); } catch (NotFoundException expected) { }
        jfs.append("/var/log/app.log", " | ok");
        FileSystem rebuilt = null;
        try { rebuilt = JournaledFs.replay(journal); }
        catch (FsException e) { System.out.println("     replay crashed: " + e.getMessage()); }
        check(rebuilt != null && rebuilt.readString("/var/log/app.log").equals(live.readString("/var/log/app.log"))
              && rebuilt.find("/", NodeFilter.ANY).equals(live.find("/", NodeFilter.ANY)),
              "the journal holds only what succeeded (" + journal.replay().size() + " lines), so the replay equals the live tree");

        // 14. a restore that cannot happen leaves the file in the trash, still restorable and still purgeable
        FileSystem tfs = new FileSystem();
        tfs.mkdirs("/home");
        tfs.putFile("/home/report.txt", "v1");
        Trash trash = new Trash(tfs);
        String id = trash.delete("/home/report.txt", 0);
        tfs.putFile("/home/report.txt", "v2");                              // somebody reuses the name
        try { trash.restore(id); check(false, "restoring onto a name that is taken again must be refused"); }
        catch (AlreadyExistsException e) { check(true, "restoring onto a name that is taken again is refused"); }
        check(trash.ids().contains(id) && tfs.exists("/.trash/" + id), "and the item is still in the trash, not lost between the two steps");
        tfs.delete("/home/report.txt", false);
        try { trash.restore(id); } catch (FsException e) { /* checked on the next line */ }
        check(tfs.exists("/home/report.txt") && tfs.readString("/home/report.txt").equals("v1") && trash.ids().isEmpty(),
              "once the name is free again, the same restore works");

        // 15. a lock per directory: changes in two folders run at the same time, and a change above them waits
        StripedNamespace striped = new StripedNamespace();
        CyclicBarrier bothInside = new CyclicBarrier(2);
        AtomicBoolean overlapped = new AtomicBoolean(true);
        Runnable meet = () -> { try { bothInside.await(2, TimeUnit.SECONDS); } catch (Exception e) { overlapped.set(false); } };
        Thread s1 = new Thread(() -> striped.withDirLocked("/var/a", meet)), s2 = new Thread(() -> striped.withDirLocked("/var/b", meet));
        s1.start(); s2.start(); s1.join(); s2.join();
        check(overlapped.get(), "a change in /var/a and one in /var/b held their locks at the same time: / and /var are shared");
        CountDownLatch inside = new CountDownLatch(1), leave = new CountDownLatch(1);
        Thread holder = new Thread(() -> striped.withDirLocked("/var/a", () -> {
            inside.countDown(); try { leave.await(); } catch (InterruptedException ignored) { } }));
        holder.start(); inside.await();
        AtomicBoolean varChanged = new AtomicBoolean(false);
        Thread above = new Thread(() -> striped.withDirLocked("/var", () -> varChanged.set(true)));
        above.start(); above.join(200);
        boolean waited = !varChanged.get();
        leave.countDown(); holder.join(); above.join();
        check(waited && varChanged.get(), "while /var/a is being changed, a change to /var's own names waits, then runs");

        // 16. a page of a big directory is read off the sorted map, so paging never copies every name
        FileSystem big = new FileSystem();
        big.mkdirs("/big");
        for (int i = 0; i < 100_000; i++) big.putFile(String.format("/big/f%06d", i), "");
        long t16 = System.nanoTime();
        int listed = 0;
        String cursor = null;
        do { BigTree.Page pg = BigTree.page(big, "/big", cursor, 50); listed += pg.names().size(); cursor = pg.next(); } while (cursor != null);
        long pagedMs = (System.nanoTime() - t16) / 1_000_000;
        check(listed == 100_000 && pagedMs < 400,
              "2,000 pages of 50 listed all 100,000 names in " + pagedMs + " ms: a page costs O(log k + 50), not a copy of k");

        // 17. with symlinks, ".." is the parent of where the walk really is, not a text edit on the path
        DirNode sroot = new DirNode("", 0), realDir = new DirNode("real", 0);
        sroot.put(realDir);
        realDir.put(new DirNode("inner", 0));
        FileNode xFile = new FileNode("x.txt", 0);
        realDir.put(xFile);
        sroot.put(new SymlinkNode("deep", "/real/inner", 0));
        FsNode got = null;
        try { got = SymlinkResolver.resolve(sroot, "/deep/../x.txt"); } catch (FsException e) { /* checked on the next line */ }
        check(got == xFile, "/deep/../x.txt, with /deep a link to /real/inner, is /real/x.txt: the parent of the link's target");

        // 18. LeetCode 588: the example from the problem, then two first writers racing on a missing file keep both texts
        LeetCode588 lc = new LeetCode588();
        check(lc.ls("/").isEmpty(), "588: ls / on an empty file system is []");
        lc.mkdir("/a/b/c");
        lc.addContentToFile("/a/b/c/d", "hello");
        check(lc.ls("/").equals(List.of("a")) && lc.readContentFromFile("/a/b/c/d").equals("hello")
              && lc.ls("/a/b/c/d").equals(List.of("d")), "588: ls, mkdir, addContentToFile and readContentFromFile match the problem's example");
        int lost18 = 0;
        for (int round = 0; round < 50; round++) {
            LeetCode588 race18 = new LeetCode588();
            CountDownLatch go18 = new CountDownLatch(1);
            List<Thread> two = new ArrayList<>();
            for (String text : List.of("A", "B"))
                two.add(new Thread(() -> { try { go18.await(); } catch (InterruptedException ignored) { } race18.addContentToFile("/x/y/log.txt", text); }));
            two.forEach(Thread::start);
            go18.countDown();
            for (Thread t : two) t.join();
            String body = race18.readContentFromFile("/x/y/log.txt");
            if (!body.equals("AB") && !body.equals("BA")) lost18++;
        }
        check(lost18 == 0, "50 races of two first writers: every file ends with both texts, because create-or-append is one step");
        FileSystem strict = new FileSystem();
        strict.mkdir("/x");
        int refused18 = 0;
        try { strict.mkdir("/x"); } catch (AlreadyExistsException e) { refused18++; }
        try { strict.mkdir("/y/z"); } catch (NotFoundException e) { refused18++; }
        check(refused18 == 2 && !strict.exists("/y"), "strict mkdir makes one level: a taken name and a missing parent both throw");

        // 19. cd and pwd: absolute, relative, ~ and .., a failed cd changes nothing, and Uber's "*"
        FileSystem shfs = new FileSystem();
        shfs.mkdirs("/home/h/docs");
        shfs.mkdirs("/var/log");
        shfs.putFile("/var/log/app.log", "x");
        Shell shell = new Shell(shfs, "/home/h");
        shell.cd("/var"); shell.cd("log"); shell.cd("../../home/./h");
        check(shell.pwd().equals("/home/h"), "cd takes absolute and relative paths, and . and .. fold: " + shell.pwd());
        shell.cd("~/docs");
        check(shell.pwd().equals("/home/h/docs"), "~ is the home folder: " + shell.pwd());
        shell.cd("../../../../..");
        check(shell.pwd().equals("/"), ".. above the root stays at /");
        int refused19 = 0;
        try { shell.cd("nope"); } catch (NotFoundException e) { refused19++; }
        try { shell.cd("/var/log/app.log"); } catch (NotADirectoryException e) { refused19++; }
        check(refused19 == 2 && shell.pwd().equals("/"), "cd to a missing path or to a file throws and leaves pwd where it was");
        shell.cd("/home");
        shell.cdGlob("*/docs");
        check(shell.pwd().equals("/home/h/docs"), "* stood for the child folder h: /home + */docs is " + shell.pwd());

        // 20. du in O(1): the kept totals always equal a slow recount, with eight threads writing and a folder moving
        SizedFolder top = new SizedFolder("", null);
        ExecutorService pool20 = Executors.newFixedThreadPool(8);
        List<Future<?>> jobs20 = new ArrayList<>();
        for (int t = 0; t < 8; t++) {
            final int n = t;
            jobs20.add(pool20.submit(() -> {
                SizedFolder mine = top.folder("var").folder("t" + n);
                for (int i = 0; i < 500; i++) mine.putFile("f" + (i % 50), i);   // new files and resized ones
                return null;
            }));
        }
        for (Future<?> f : jobs20) f.get();
        pool20.shutdown();
        top.folder("var").folder("t3").moveTo(top.folder("home"));
        top.folder("var").folder("t5").deleteFile("f7");
        check(top.du() == top.recount() && top.folder("var").du() == top.folder("var").recount()
              && top.folder("home").du() == top.folder("home").recount(),
              "du read " + top.du() + " in O(1) and a recount agrees, at / and at both ends of a move");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
