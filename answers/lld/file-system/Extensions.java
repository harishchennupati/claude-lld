import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

// Reference code for every follow-up on page 05. Each block is self-contained and is exercised by ExtDemo at the
// bottom, so none of it can rot. Compile with: javac Main.java Extensions.java FailureTests.java

// ---- ext: a read-only subtree -- the second rule, which is how you show that rules stack
/**
 * "Now make /etc read-only." A second WriteGuard, composed with the quota through WriteGuard.allOf: neither rule
 * knows the other exists, and FileSystem is not opened to add it. Every change asks the guard, so this refuses a
 * byte write, a mkdir, a move or a delete under /etc -- and an rm -r or mv of a folder ABOVE /etc, which would
 * take /etc with it. It throws an FsException like every other refusal, so one catch handles both rules.
 */
final class ReadOnlySubtreeGuard implements WriteGuard {
    private final FsPath frozen;
    ReadOnlySubtreeGuard(String prefix) { this.frozen = FsPath.of(prefix); }
    @Override public void check(WriteRequest r) {
        FsPath p = FsPath.of(r.path());
        boolean inside = p.startsWith(frozen);
        boolean takesItAlong = (r.mode() == WriteMode.MOVE || r.mode() == WriteMode.DELETE) && frozen.startsWith(p);
        if (inside || takesItAlong) throw new FsException(frozen + " is read-only, so " + p + " cannot change");
    }
}

// ---- ext: symlinks -- a third kind of node, and the path walk takes over ".."
/**
 * A name that points at another path instead of at bytes. ls, find, the guards and the watchers keep treating it
 * as a node with a name and a size. The target is kept exactly as written: its ".." is resolved when it is walked.
 */
final class SymlinkNode extends FsNode {
    private final String target;
    SymlinkNode(String name, String target, long now) {
        super(name, now);
        if (!target.startsWith("/")) throw new FsException("a link target must be absolute here: " + target);
        this.target = target;
    }
    String target() { return target; }
    @Override boolean isDirectory() { return false; }
    /** A link is a name, not bytes; its own size is the length of the target string, as on a real file system. */
    @Override long sizeBytes() { return target.length(); }
}

/**
 * The changed path walk. It keeps the folders it is really in on a stack, so ".." means the parent of the folder
 * the walk has reached: /shortcut/.. is the parent of the link's TARGET, not the root. That is why FsPath's early
 * folding of ".." has to go once links exist (Java's Path.normalize() carries the same warning). When a segment is
 * a link, its target's segments are put in front of the ones still to walk and the walk restarts at the root,
 * counting hops; after MAX_HOPS it gives up, so a loop (/a -> /b, /b -> /a) is an error instead of a hang.
 */
final class SymlinkResolver {
    static final int MAX_HOPS = 40;                                      // the same limit Linux uses
    /** Resolve a raw absolute path through any number of links. Caller holds the namespace read lock. */
    static FsNode resolve(DirNode root, String raw) {
        if (raw == null || !raw.startsWith("/")) throw new FsException("path must be absolute: " + raw);
        Deque<String> todo = new ArrayDeque<>(Arrays.asList(raw.split("/")));
        Deque<FsNode> where = new ArrayDeque<>(List.of(root));             // the folders the walk is really in
        int hops = 0;
        while (!todo.isEmpty()) {
            String seg = todo.pollFirst();
            if (seg.isEmpty()) continue;
            if (!where.peek().isDirectory()) throw new NotADirectoryException(raw);
            if (seg.equals(".")) continue;
            if (seg.equals("..")) { if (where.size() > 1) where.pop(); continue; }   // the real parent; clamps at the root
            FsNode next = ((DirNode) where.peek()).child(seg);
            if (next == null) throw new NotFoundException(raw);
            if (next instanceof SymlinkNode link) {
                if (++hops > MAX_HOPS) throw new FsException("too many levels of symbolic links: " + raw);
                String[] target = link.target().split("/");
                for (int j = target.length - 1; j >= 0; j--) todo.addFirst(target[j]);
                where.clear(); where.push(root);                           // an absolute target: restart at the root
                continue;
            }
            where.push(next);
        }
        return where.peek();
    }
}

// ---- ext: hard links -- two names, one set of bytes, one refcount
/**
 * The bytes, split out from the name. A hard link is a second directory entry pointing at the same inode; the
 * bytes die when the last name goes, which is what the refcount counts.
 */
final class Inode {
    private final ReentrantLock lock = new ReentrantLock();
    private byte[] content;
    private int links = 0;
    Inode(byte[] content) { this.content = content; }
    void link() { lock.lock(); try { links++; } finally { lock.unlock(); } }
    /** Drop one name. Returns true when that was the last one and the bytes were released. */
    boolean unlink() {
        lock.lock();
        try { if (--links == 0) { content = new byte[0]; return true; } return false; }
        finally { lock.unlock(); }
    }
    int links() { lock.lock(); try { return links; } finally { lock.unlock(); } }
    byte[] read() { lock.lock(); try { return content.clone(); } finally { lock.unlock(); } }
    long size() { lock.lock(); try { return content.length; } finally { lock.unlock(); } }
}

/** A directory entry that shares its bytes with any other entry pointing at the same inode. */
final class LinkedFile extends FsNode {
    private final Inode inode;
    LinkedFile(String name, Inode inode, long now) { super(name, now); this.inode = inode; inode.link(); }
    Inode inode() { return inode; }
    @Override boolean isDirectory() { return false; }
    @Override long sizeBytes() { return inode.size(); }
    /** du must count shared bytes once, so a real du folds over a set of inode identities, not over names. */
    static long du(Collection<LinkedFile> entries) {
        Set<Inode> seen = Collections.newSetFromMap(new IdentityHashMap<>());
        long total = 0;
        for (LinkedFile f : entries) if (seen.add(f.inode())) total += f.inode().size();
        return total;
    }
}

// ---- ext: users and permissions -- the rule that changes, behind one interface, checked before the call
/** Who is asking. Threaded through the API rather than read from a thread local, so a test can be any user. */
record Principal(String user, Set<String> groups) {
    static Principal of(String user) { return new Principal(user, Set.of()); }
}

/** What they want to do with the path. Two verbs is enough for the owner/mode model. */
enum Access { READ, WRITE }

/** The permission rule. One method, so it composes with the other rules and a test hands in a lambda. */
@FunctionalInterface
interface AccessPolicy {
    void check(Principal who, String path, Access what);
    AccessPolicy ALLOW_ALL = (who, path, what) -> {};
}

/**
 * Owner plus mode bits, the Unix model in twenty lines: each path has an owner and two booleans (may others
 * read, may others write). Anything more elaborate -- groups, ACLs, inherited permissions -- is a different
 * implementation of the same interface.
 */
final class OwnerMode implements AccessPolicy {
    private record Entry(String owner, boolean otherRead, boolean otherWrite) {}
    private final Map<String, Entry> table = new ConcurrentHashMap<>();
    /** Record who owns a path and what everybody else may do with it. */
    void chown(String path, String owner, boolean otherRead, boolean otherWrite) { table.put(path, new Entry(owner, otherRead, otherWrite)); }
    @Override public void check(Principal who, String path, Access what) {
        Entry e = table.get(path);
        if (e == null || e.owner().equals(who.user())) return;                       // unowned or mine
        boolean ok = what == Access.READ ? e.otherRead() : e.otherWrite();
        if (!ok) throw new FsException("permission denied: " + who.user() + " cannot " + what + " " + path);
    }
}

/**
 * A thin wrapper over the file system that asks the policy first and then delegates. The file system itself does
 * not change at all; it does not know what a user is.
 */
final class SecureFs {
    private final FileSystem fs;
    private final AccessPolicy policy;
    SecureFs(FileSystem fs, AccessPolicy policy) { this.fs = fs; this.policy = policy; }
    void putFile(Principal who, String path, String content) { policy.check(who, path, Access.WRITE); fs.putFile(path, content); }
    String read(Principal who, String path) { policy.check(who, path, Access.READ); return fs.readString(path); }
    void delete(Principal who, String path, boolean recursive) { policy.check(who, path, Access.WRITE); fs.delete(path, recursive); }
}

// ---- ext: trash and restore -- delete grows a life cycle, built out of move
/**
 * "Make delete recoverable" means a file has states, not a boolean. Deleting becomes a move into a hidden
 * directory: the name leaves the visible tree, the bytes survive, restoring is the move back, and purging is the
 * only thing that actually frees memory. Every step reuses a method that already exists.
 */
final class Trash {
    private record Item(String originalPath, long deletedAtMs) {}
    private final FileSystem fs;
    private final Map<String, Item> items = new ConcurrentHashMap<>();   // many threads delete and restore at once
    private final AtomicLong ids = new AtomicLong();
    Trash(FileSystem fs) { this.fs = fs; fs.mkdirs("/.trash"); }

    /** LIVE -> TRASHED: the name moves out of the visible tree and the bytes stay exactly where they were. */
    String delete(String path, long nowMs) {
        String id = "t" + ids.incrementAndGet();
        fs.move(path, "/.trash/" + id);                                  // if this throws, nothing was recorded
        items.put(id, new Item(path, nowMs));
        return id;
    }
    /**
     * TRASHED -> LIVE: the same move, backwards. Claim the record first (a second restore or a purge now finds
     * nothing), then move; if the move fails -- the old path is taken again, or its folder is gone -- put the
     * record back, so the file stays in the trash and can be restored later or purged.
     */
    void restore(String id) {
        Item it = items.remove(id);
        if (it == null) throw new NotFoundException("/.trash/" + id);
        try { fs.move("/.trash/" + id, it.originalPath()); }
        catch (RuntimeException e) { items.put(id, it); throw e; }
    }
    /** TRASHED -> PURGED: the only step that frees bytes. A sweeper calls this on a timer. */
    int purge(long olderThanMs, long nowMs) {
        int n = 0;
        for (Map.Entry<String, Item> e : items.entrySet()) {
            if (nowMs - e.getValue().deletedAtMs() < olderThanMs) continue;
            if (!items.remove(e.getKey(), e.getValue())) continue;         // a restore claimed it first
            fs.delete("/.trash/" + e.getKey(), true);
            n++;
        }
        return n;
    }
    List<String> ids() { return new ArrayList<>(new TreeSet<>(items.keySet())); }
}

// ---- ext: random access and big files -- one byte[] becomes a list of chunks
/**
 * Replace a file's single array with a list of fixed chunks and three costs change: append stops copying the
 * whole file (amortised O(1) instead of O(n)), a write at an offset touches one chunk, and a ten-megabyte file
 * stops needing ten contiguous megabytes. Read, size and version keep their meaning, so nothing above notices.
 */
final class ChunkedContent {
    private final int chunkSize;
    private final List<byte[]> chunks = new ArrayList<>();
    private long size = 0;
    ChunkedContent(int chunkSize) { this.chunkSize = chunkSize; }

    long size() { return size; }
    /** Amortised O(1): fill the tail chunk, then add chunks. No copy of what is already there. */
    void append(byte[] b) {
        int off = 0;
        while (off < b.length) {
            int inTail = (int) (size % chunkSize);
            if (inTail == 0) chunks.add(new byte[chunkSize]);
            byte[] tail = chunks.get(chunks.size() - 1);
            int n = Math.min(chunkSize - inTail, b.length - off);
            System.arraycopy(b, off, tail, inTail, n);
            off += n; size += n;
        }
    }
    /** A write at an offset inside the file: find the chunk, write into it. O(bytes written), not O(file). */
    void writeAt(long offset, byte[] b) {
        if (offset + b.length > size) throw new FsException("write past the end of the file");
        int off = 0;
        while (off < b.length) {
            long pos = offset + off;
            byte[] chunk = chunks.get((int) (pos / chunkSize));
            int in = (int) (pos % chunkSize);
            int n = Math.min(chunkSize - in, b.length - off);
            System.arraycopy(b, off, chunk, in, n);
            off += n;
        }
    }
    /** Read a window. The caller never learns how many chunks it crossed. */
    byte[] read(long offset, int len) {
        byte[] out = new byte[(int) Math.min(len, size - offset)];
        for (int i = 0; i < out.length; i++) {
            long pos = offset + i;
            out[i] = chunks.get((int) (pos / chunkSize))[(int) (pos % chunkSize)];
        }
        return out;
    }
}

// ---- ext: many readers, one writer -- and the optimistic write for a human in the loop
/**
 * A file whose bytes are under a ReadWriteLock instead of a plain lock: any number of readers at once, one
 * writer alone. Worth it when reads dominate; the plain lock in Main is the simpler default.
 *
 * compareAndWrite is the other half. You cannot hold a lock across a human editing a config for thirty seconds,
 * so the caller reads a version, edits at leisure, and writes back only if nobody else got there first.
 */
final class RwFile {
    private final ReentrantReadWriteLock lock = new ReentrantReadWriteLock();
    private byte[] content = new byte[0];
    private final AtomicLong version = new AtomicLong();

    /** Many of these run at the same time. */
    byte[] read() { lock.readLock().lock(); try { return content.clone(); } finally { lock.readLock().unlock(); } }
    long version() { return version.get(); }
    /** Optimistic: false means somebody else wrote while you were thinking, so re-read and try again. */
    boolean compareAndWrite(long expectedVersion, byte[] bytes) {
        lock.writeLock().lock();
        try {
            if (version.get() != expectedVersion) return false;
            content = bytes.clone(); version.incrementAndGet();
            return true;
        } finally { lock.writeLock().unlock(); }
    }
}

// ---- ext: persistence -- a journal of every change that succeeded, and a replay that rebuilds the tree
/** The mutations worth replaying. Reads are not in the list, which is why the journal stays small. */
enum OpKind { MKDIRS, PUT, APPEND, MOVE, DELETE }

/** One line of the journal: what was done, to what, with what. Ordered by seq. */
record JournalEntry(long seq, OpKind op, String path, String arg) {}

/** Where the journal lives. In memory here; a file, then a replicated log, later. */
interface Journal {
    void append(JournalEntry e);
    List<JournalEntry> replay();
}

/** The in-memory journal, which is enough to prove the replay is correct. */
final class InMemoryJournal implements Journal {
    private final List<JournalEntry> lines = new CopyOnWriteArrayList<>();
    @Override public void append(JournalEntry e) { lines.add(e); }
    @Override public List<JournalEntry> replay() { return List.copyOf(lines); }
}

/**
 * The file system with a journal beside it: every change that SUCCEEDED is written down, in order. Apply, then
 * journal, under one lock, so the journal's order is the order things really happened. A refused call (no such
 * file, over quota) throws before its line is written, so it can never come back on replay. Redis's append-only
 * file works the same way. Crash, restart, replay the journal into a fresh file system and you are where you were.
 */
final class JournaledFs {
    private final FileSystem fs;
    private final Journal journal;
    private final AtomicLong seq = new AtomicLong();
    private final ReentrantLock order = new ReentrantLock();
    JournaledFs(FileSystem fs, Journal journal) { this.fs = fs; this.journal = journal; }

    void mkdirs(String path) { run(OpKind.MKDIRS, path, null, () -> fs.mkdirs(path)); }
    void putFile(String path, String content) { run(OpKind.PUT, path, content, () -> fs.putFile(path, content)); }
    void append(String path, String more) { run(OpKind.APPEND, path, more, () -> fs.append(path, more)); }
    void move(String from, String to) { run(OpKind.MOVE, from, to, () -> fs.move(from, to)); }
    void delete(String path, boolean recursive) { run(OpKind.DELETE, path, String.valueOf(recursive), () -> fs.delete(path, recursive)); }

    /**
     * Apply, then journal. If the apply throws, no line is written. A crash between the two loses that one change,
     * and its caller never got an answer, so nothing a caller was told has been lost.
     */
    private void run(OpKind op, String path, String arg, Runnable body) {
        order.lock();
        try { body.run(); journal.append(new JournalEntry(seq.incrementAndGet(), op, path, arg)); }
        finally { order.unlock(); }
    }

    /** Rebuild a file system from the log. This is what "survive a restart" means. */
    static FileSystem replay(Journal journal) {
        FileSystem out = new FileSystem();
        for (JournalEntry e : journal.replay()) {
            switch (e.op()) {
                case MKDIRS -> out.mkdirs(e.path());
                case PUT -> out.putFile(e.path(), e.arg());
                case APPEND -> out.append(e.path(), e.arg());
                case MOVE -> out.move(e.path(), e.arg());
                case DELETE -> out.delete(e.path(), Boolean.parseBoolean(e.arg()));
            }
        }
        return out;
    }
}

// ---- ext: a slow watcher must not freeze the namespace -- a bounded queue, and a counter for what it dropped
/**
 * The file system hands each event to this wrapper after the unlock, on the writer's thread (two writers may hand
 * theirs over in either order); it puts them on a queue of its own and one thread drains it, so a subscriber that
 * takes two seconds now delays only itself.
 *
 * The queue is BOUNDED on purpose. An unbounded queue turns a slow subscriber into an out-of-memory error under a
 * write storm, which is the failure nobody sees coming. Full means drop and count: the file system must never
 * block on a subscriber, so the only honest choice is to lose the notification and say how many were lost.
 * That makes the stream at-most-once -- a watcher that must not miss anything reads the journal instead.
 */
final class AsyncWatcher implements FsWatcher, AutoCloseable {
    private final BlockingQueue<FsEvent> queue;
    private final Thread worker;
    private final AtomicLong dropped = new AtomicLong();
    private volatile boolean running = true;

    AsyncWatcher(int capacity, FsWatcher delegate) {
        this.queue = new ArrayBlockingQueue<>(capacity);
        this.worker = new Thread(() -> {
            while (running || !queue.isEmpty()) {
                try {
                    FsEvent e = queue.poll(20, TimeUnit.MILLISECONDS);
                    if (e != null) delegate.onEvent(e);
                } catch (InterruptedException ie) { Thread.currentThread().interrupt(); return; }
                catch (RuntimeException ignored) { }                    // a broken subscriber is not a failed write
            }
        }, "fs-watcher");
        worker.setDaemon(true);
        worker.start();
    }

    /** Never blocks: this runs on the writer's thread, just after the unlock. After close() it only counts. */
    @Override public void onEvent(FsEvent e) { if (!running || !queue.offer(e)) dropped.incrementAndGet(); }
    /** The metric worth exporting. A number above zero means the subscriber cannot keep up. */
    long dropped() { return dropped.get(); }
    /** Stop accepting, drain what is queued, and join the thread. */
    @Override public void close() throws InterruptedException { running = false; worker.join(2000); }
}

// ---- ext: millions of files -- a page of names, and top-N without sorting the tree
/**
 * The read APIs a big tree forces. ls returns a page and a cursor instead of two hundred thousand names -- read
 * straight off the sorted map, so a page costs O(log k + n) -- and "the ten biggest files under /var" is the same
 * single walk folded into a bounded heap, never a sort of everything.
 */
final class BigTree {
    /** One page of a directory listing: the names after the cursor, plus the next cursor or null. */
    record Page(List<String> names, String next) {}
    static Page page(FileSystem fs, String dir, String after, int n) {
        if (n <= 0) throw new IllegalArgumentException("a page holds at least one name");
        List<String> names = fs.ls(dir, after, n + 1);            // one extra name says whether another page exists
        boolean more = names.size() > n;
        List<String> page = more ? names.subList(0, n) : names;
        return new Page(List.copyOf(page), more ? page.get(n - 1) : null);
    }

    /**
     * The n biggest files under a path, in one walk and n slots of memory. The predicate is called once per node
     * under the read lock, so a predicate that records instead of answering is a fold over the walk; if that
     * feels like abuse, the honest version makes walk() public and takes a visitor.
     */
    static List<String> topNBySize(FileSystem fs, String from, int n) {
        PriorityQueue<Map.Entry<String, Long>> heap = new PriorityQueue<>(Map.Entry.comparingByValue());
        fs.find(from, (path, node) -> {
            if (node.isDirectory()) return false;
            heap.add(Map.entry(path, node.sizeBytes()));
            if (heap.size() > n) heap.poll();                       // the heap never holds more than n
            return false;
        });
        List<String> out = new ArrayList<>();
        while (!heap.isEmpty()) out.add(0, heap.poll().getKey());
        return out;
    }
}

// ---- ext: one namespace lock is the bottleneck -- a lock per directory, taken from the root down
/**
 * Rung two of the ladder. Replace the single namespace lock with a read-write lock per directory. To change the
 * names inside one folder, take the READ side of every folder above it, from the root down, and the WRITE side of
 * that folder only. mkdir /var/a/x and mkdir /var/b/y then share / and /var and run at the same time, while a
 * change to /var's own names (moving /var/a) waits for both. Everyone locks from the root down, so no two threads
 * can hold two locks in opposite orders. A move between two folders needs two write sides, which is the hard
 * part (Linux keeps one extra per-volume lock just for such renames). Real code keeps the lock on the DirNode.
 */
final class StripedNamespace {
    private final Map<String, ReentrantReadWriteLock> locks = new ConcurrentHashMap<>();
    private ReentrantReadWriteLock lockFor(FsPath p) { return locks.computeIfAbsent(p.toString(), k -> new ReentrantReadWriteLock()); }

    /** Run body, which changes the names inside dir: shared locks on the way down, the exclusive one on dir. */
    void withDirLocked(String dir, Runnable body) {
        FsPath p = FsPath.of(dir);
        List<Lock> held = new ArrayList<>();
        try {
            for (int i = 0; i <= p.depth(); i++) {
                ReentrantReadWriteLock rw = lockFor(p.prefix(i));
                Lock l = i < p.depth() ? rw.readLock() : rw.writeLock();   // parent first, always
                l.lock();
                held.add(l);
            }
            body.run();
        } finally {
            for (int i = held.size() - 1; i >= 0; i--) held.get(i).unlock();
        }
    }
}

// ---- ext: LeetCode 588 -- the four calls, mapped onto the file system
/**
 * "Design In-Memory File System" (LeetCode 588) as interviewers hand it out. Three calls already exist; the fourth,
 * addContentToFile, is create-or-append, and 588 also makes any missing folders on the way.
 */
final class LeetCode588 {
    private final FileSystem fs = new FileSystem();
    /** Sorted names; a file path lists just its own name, as 588 asks. */
    List<String> ls(String path) { return fs.ls(path); }
    void mkdir(String path) { fs.mkdirs(path); }
    /** Make the missing folders, then create-or-append in ONE locked step: never append, catch "not found", then create. */
    void addContentToFile(String filePath, String content) {
        fs.mkdirs(FsPath.of(filePath).parent().toString());
        fs.addContent(filePath, content);
    }
    String readContentFromFile(String filePath) { return fs.readString(filePath); }
}

// ---- ext: cd and pwd -- a working directory, relative paths, "~", and Uber's "*"
/**
 * A shell session. The one piece of state it owns is the working directory, and it turns every path the user types
 * into an absolute one before the file system sees it: "/x" is absolute, "~" is home, anything else starts at the
 * working directory. FsPath then folds "." and ".." as before, clamping at the root.
 */
final class Shell {
    private final FileSystem fs;
    private final FsPath home;
    private volatile FsPath cwd = FsPath.ROOT;
    Shell(FileSystem fs, String home) { this.fs = fs; this.home = FsPath.of(home); }

    String pwd() { return cwd.toString(); }
    /** What the user typed, as an absolute path. */
    FsPath absolute(String typed) {
        if (typed.startsWith("/")) return FsPath.of(typed);
        if (typed.equals("~") || typed.startsWith("~/")) return FsPath.of(home + typed.substring(1));
        return FsPath.of(cwd + "/" + typed);
    }
    /** Check first, then move: a cd to a missing path or to a file throws and leaves the working directory where it was. */
    void cd(String typed) {
        FsPath target = absolute(typed);
        if (!fs.exists(target.toString())) throw new NotFoundException(target.toString());
        if (!fs.isDirectory(target.toString())) throw new NotADirectoryException(target.toString());
        cwd = target;
    }
    void mkdir(String typed) { fs.mkdirs(absolute(typed).toString()); }
    List<String> ls() { return fs.ls(cwd.toString()); }

    /**
     * Uber's twist: a "*" segment may stand for ".", ".." or any child folder. Try those choices in that order, depth
     * first; the first path that leads to a real folder wins. If none does, cd fails and nothing moves.
     */
    void cdGlob(String typed) {
        FsPath found = firstMatch(typed.startsWith("/") ? FsPath.ROOT : cwd, typed.split("/"), 0);
        if (found == null) throw new NotFoundException(typed);
        cwd = found;
    }
    private FsPath firstMatch(FsPath at, String[] segs, int i) {
        if (i == segs.length) return at;
        List<String> choices = new ArrayList<>();
        if (segs[i].equals("*")) {
            choices.addAll(List.of(".", ".."));
            for (String c : fs.ls(at.toString())) if (fs.isDirectory(at.child(c).toString())) choices.add(c);
        } else choices.add(segs[i]);
        for (String c : choices) {
            FsPath next = c.isEmpty() || c.equals(".") ? at : c.equals("..") ? at.parent() : at.child(c);
            if (!fs.isDirectory(next.toString())) continue;
            FsPath found = firstMatch(next, segs, i + 1);
            if (found != null) return found;
        }
        return null;
    }
}

// ---- ext: du in O(1) -- each folder keeps the bytes under it, and every write pays O(depth)
/**
 * "du must be O(1) and stay right while files change." Each folder keeps an AtomicLong of the bytes under it. A file
 * that changes by delta bytes adds delta to its folder and to every folder above it, so du is one read and a write
 * costs O(depth). A move takes the folder's bytes out of every old ancestor and adds them to every new one. The
 * counters are atomic because writers to different files add to the same parent at once; in the real file system a
 * move holds the namespace write lock, so no write is half-counted while it runs.
 */
final class SizedFolder {
    private final String name;
    private volatile SizedFolder parent;
    private final AtomicLong bytesUnder = new AtomicLong();
    private final Map<String, SizedFolder> folders = new ConcurrentHashMap<>();
    private final Map<String, Long> files = new ConcurrentHashMap<>();
    SizedFolder(String name, SizedFolder parent) { this.name = name; this.parent = parent; }

    SizedFolder folder(String n) { return folders.computeIfAbsent(n, k -> new SizedFolder(k, this)); }
    /** Create or resize a file here; the difference travels up to the root. O(depth). */
    void putFile(String n, long size) { Long old = files.put(n, size); addUp(size - (old == null ? 0 : old)); }
    void deleteFile(String n) { Long old = files.remove(n); if (old != null) addUp(-old); }
    /** Move this folder under another: its bytes leave every old ancestor and arrive at every new one. O(depth). */
    void moveTo(SizedFolder to) {
        long b = bytesUnder.get();
        parent.folders.remove(name); parent.addUp(-b);
        parent = to; to.folders.put(name, this); to.addUp(b);
    }
    /** O(1): the answer is already there. */
    long du() { return bytesUnder.get(); }
    /** The slow answer, a walk; a test compares it with du(). */
    long recount() {
        long s = 0;
        for (long f : files.values()) s += f;
        for (SizedFolder c : folders.values()) s += c.recount();
        return s;
    }
    private void addUp(long delta) { for (SizedFolder f = this; f != null; f = f.parent) f.bytesUnder.addAndGet(delta); }
}

/** Runs every extension above so that none of them can quietly rot. */
class ExtDemo {
    public static void main(String[] args) throws Exception {
        long now = 1_700_000_000_000L;

        // symlinks, and a loop that ends in an error instead of a hang
        DirNode root = new DirNode("", now);
        DirNode real = new DirNode("real", now); root.put(real);
        FileNode note = new FileNode("note.txt", now); note.lock();
        try { note.setContentLocked("through a link".getBytes(StandardCharsets.UTF_8), now); } finally { note.unlock(); }
        real.put(note);
        root.put(new SymlinkNode("shortcut", "/real", now));
        System.out.println("symlink: /shortcut/note.txt -> \""
            + new String(((FileNode) SymlinkResolver.resolve(root, "/shortcut/note.txt")).read(), StandardCharsets.UTF_8) + "\"");
        DirNode inner = new DirNode("inner", now); real.put(inner);
        root.put(new SymlinkNode("deep", "/real/inner", now));
        System.out.println("symlink then ..: /deep/../note.txt is " + SymlinkResolver.resolve(root, "/deep/../note.txt").name()
            + " in /real (the parent of the target), not /note.txt");
        root.put(new SymlinkNode("a", "/b", now));
        root.put(new SymlinkNode("b", "/a", now));
        try { SymlinkResolver.resolve(root, "/a/x"); }
        catch (FsException e) { System.out.println("symlink loop: " + e.getMessage()); }

        // hard links: two names, one set of bytes
        Inode shared = new Inode("one copy of the bytes".getBytes(StandardCharsets.UTF_8));
        LinkedFile n1 = new LinkedFile("original.txt", shared, now), n2 = new LinkedFile("backup.txt", shared, now);
        System.out.println("hard links: " + shared.links() + " names, du counts " + LinkedFile.du(List.of(n1, n2))
            + " bytes once (not " + (n1.sizeBytes() + n2.sizeBytes()) + ")");
        System.out.println("unlink one: bytes freed=" + shared.unlink() + ", unlink the other: bytes freed=" + shared.unlink());

        // two rules, stacked: a quota and a read-only subtree, neither knowing the other exists
        FileSystem fs = new FileSystem();
        fs.mkdirs("/etc");
        fs.putFile("/etc/passwd", "root:x:0");
        fs.configure(WriteGuard.allOf(new CapacityGuard(64, 1024), new ReadOnlySubtreeGuard("/etc")));
        try { fs.append("/etc/passwd", "harish:x:0"); }
        catch (FsException e) { System.out.println("two rules stacked: " + e.getMessage()); }
        fs.configure(WriteGuard.UNLIMITED);

        // permissions: the same call, two users
        OwnerMode mode = new OwnerMode();
        mode.chown("/etc/passwd", "root", true, false);
        SecureFs secure = new SecureFs(fs, mode);
        System.out.println("permissions: harish may read -> \"" + secure.read(Principal.of("harish"), "/etc/passwd") + "\"");
        try { secure.putFile(Principal.of("harish"), "/etc/passwd", "harish:x:0"); }
        catch (FsException e) { System.out.println("permissions: " + e.getMessage()); }

        // trash, restore, purge
        fs.mkdirs("/home/h");
        fs.putFile("/home/h/report.txt", "quarterly numbers");
        Trash trash = new Trash(fs);
        String id = trash.delete("/home/h/report.txt", now);
        System.out.println("trash: visible=" + fs.exists("/home/h/report.txt") + ", bytes still there=" + fs.exists("/.trash/" + id));
        trash.restore(id);
        System.out.println("restore: \"" + fs.readString("/home/h/report.txt") + "\" back at its old path");
        trash.delete("/home/h/report.txt", now);
        System.out.println("purge after a day: " + trash.purge(86_400_000L, now + 2 * 86_400_000L) + " item freed, trash now " + trash.ids());

        // chunked content: append without copying the file, and a write at an offset
        ChunkedContent big = new ChunkedContent(8);
        for (int i = 0; i < 5; i++) big.append("abcdefgh".getBytes(StandardCharsets.UTF_8));
        big.writeAt(10, "ZZ".getBytes(StandardCharsets.UTF_8));
        System.out.println("chunked: size=" + big.size() + ", bytes 8..16 = \""
            + new String(big.read(8, 8), StandardCharsets.UTF_8) + "\"");

        // many readers one writer, and the optimistic write
        RwFile cfg = new RwFile();
        cfg.compareAndWrite(0, "timeout=30".getBytes(StandardCharsets.UTF_8));
        long seen = cfg.version();
        cfg.compareAndWrite(seen, "timeout=60".getBytes(StandardCharsets.UTF_8));           // somebody else got there first
        System.out.println("compareAndWrite with a stale version: " + cfg.compareAndWrite(seen, "timeout=90".getBytes(StandardCharsets.UTF_8))
            + ", the file still says \"" + new String(cfg.read(), StandardCharsets.UTF_8) + "\"");

        // persistence: journal, crash, replay
        Journal journal = new InMemoryJournal();
        JournaledFs jfs = new JournaledFs(new FileSystem(), journal);
        jfs.mkdirs("/var/log");
        jfs.putFile("/var/log/app.log", "started");
        jfs.append("/var/log/app.log", " | ready");
        jfs.move("/var/log/app.log", "/var/log/app.1.log");
        FileSystem rebuilt = JournaledFs.replay(journal);
        System.out.println("replayed " + journal.replay().size() + " journal lines -> \"" + rebuilt.readString("/var/log/app.1.log") + "\"");

        // a slow watcher delays only itself, and a full queue drops instead of blocking the writer
        CountDownLatch heard = new CountDownLatch(1);
        AsyncWatcher async = new AsyncWatcher(2, e -> { try { Thread.sleep(50); } catch (InterruptedException ignored) { } heard.countDown(); });
        rebuilt.watch("/var", async);
        long t0 = System.nanoTime();
        for (int i = 0; i < 20; i++) rebuilt.putFile("/var/log/slow" + i + ".txt", "x");
        long writeUs = (System.nanoTime() - t0) / 1000;
        heard.await(2, TimeUnit.SECONDS);
        System.out.println("async watcher: 20 writes returned in " + writeUs + " us although the subscriber sleeps 50 ms each, "
            + "and the 2-slot queue dropped " + async.dropped() + " events rather than block a write");
        async.close();

        // big trees: a page of names, and the biggest files in one walk
        FileSystem farm = new FileSystem();
        farm.mkdirs("/var/data");
        for (int i = 0; i < 12; i++) farm.putFile("/var/data/f" + (char) ('a' + i) + ".bin", "x".repeat(i + 1));
        BigTree.Page p1 = BigTree.page(farm, "/var/data", null, 5);
        System.out.println("page 1 of ls: " + p1.names() + " next cursor=" + p1.next());
        System.out.println("page 2 of ls: " + BigTree.page(farm, "/var/data", p1.next(), 5).names());
        System.out.println("3 biggest under /var: " + BigTree.topNBySize(farm, "/var", 3));

        // a lock per directory: shared on the way down, exclusive on the folder that changes
        StripedNamespace striped = new StripedNamespace();
        striped.withDirLocked("/var/data", () -> System.out.println("striped: read-locked / and /var, write-locked /var/data, in that order"));

        // LeetCode 588, the example from the problem statement
        LeetCode588 lc = new LeetCode588();
        lc.mkdir("/a/b/c");
        lc.addContentToFile("/a/b/c/d", "hello");
        System.out.println("588: ls / = " + lc.ls("/") + ", read /a/b/c/d = \"" + lc.readContentFromFile("/a/b/c/d") + "\"");

        // cd and pwd, then Uber's "*"
        FileSystem shfs = new FileSystem();
        shfs.mkdirs("/home/h/docs");
        Shell shell = new Shell(shfs, "/home/h");
        shell.cd("/home"); shell.cd("h/../h/./docs");
        String first = shell.pwd();
        shell.cd("~"); shell.cd("../../../..");
        String clamped = shell.pwd();
        shell.cd("/home"); shell.cdGlob("*/docs");
        System.out.println("cd: " + first + ", then ~ and ../../../.. -> " + clamped + ", then */docs from /home -> " + shell.pwd());

        // du in O(1)
        SizedFolder rootDir = new SizedFolder("", null);
        rootDir.folder("var").folder("log").putFile("app.log", 700);
        rootDir.folder("var").putFile("big.bin", 300);
        rootDir.folder("var").folder("log").moveTo(rootDir.folder("home"));
        System.out.println("du in O(1): / = " + rootDir.du() + ", /var = " + rootDir.folder("var").du()
            + ", /home = " + rootDir.folder("home").du() + " (a recount says " + rootDir.recount() + ")");
    }
}
