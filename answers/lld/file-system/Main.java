import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

/**
 * What kind of change a guard is asked about: two ways to write bytes (replace every byte, add to the end) and three
 * ways to change the tree. Every change asks, so a read-only folder really is read-only. No byte offsets (a follow-up adds them).
 */
enum WriteMode { OVERWRITE, APPEND, MKDIR, MOVE, DELETE }

/** What happened to a path. Watchers are told after the lock is released, never inside it. */
enum EventKind { CREATED, WRITTEN, DELETED, MOVED }

/**
 * A file's life. LIVE = reachable by name. UNLINKED = the name is gone but somebody has it open, so the bytes
 * survive. FREED = the last handle closed and the bytes were released. Nothing skips a step.
 */
enum FileState { LIVE, UNLINKED, FREED }

/** Where time comes from. Injected, so a test can stamp a node with any instant it likes. */
interface Clock {
    long nowMs();
    /** The production clock. A test hands in its own instead. */
    Clock SYSTEM = System::currentTimeMillis;
}

// ---------------------------------------------------------------- failures, as one family

/** Every failure this file system can produce. One base class, so a caller can catch the family in one line. */
class FsException extends RuntimeException { FsException(String m) { super(m); } }
/** Nothing lives at that path. */
final class NotFoundException extends FsException { NotFoundException(String p) { super("no such file or directory: " + p); } }
/** Something already lives at that path and this call refuses to clobber it. */
final class AlreadyExistsException extends FsException { AlreadyExistsException(String p) { super("already exists: " + p); } }
/** A path walked through something that is a file, so it cannot have children. */
final class NotADirectoryException extends FsException { NotADirectoryException(String p) { super("not a directory: " + p); } }
/** The path names a directory and the caller asked for bytes. */
final class IsADirectoryException extends FsException { IsADirectoryException(String p) { super("is a directory: " + p); } }
/** rm on a directory that still has children, without the recursive flag. Loud on purpose. */
final class DirectoryNotEmptyException extends FsException { DirectoryNotEmptyException(String p) { super("directory not empty: " + p); } }
/** A write guard said no. Thrown before a single byte moves. */
final class QuotaExceededException extends FsException { QuotaExceededException(String m) { super(m); } }
/** A move that would orphan a subtree, or move a node onto itself. */
final class InvalidMoveException extends FsException { InvalidMoveException(String m) { super(m); } }

// ---------------------------------------------------------------- the path, parsed exactly once

/**
 * An absolute path, normalised once at the edge of the API into an immutable list of segments: empty segments and
 * "." vanish, ".." pops, and ".." above the root clamps at the root. After this class no method in the system ever
 * sees a slash, which is why ".." cannot mean two different things in two different methods. (Folding ".." early is
 * right for a strict tree; once symlinks exist, ".." must be applied during the walk -- see Extensions.)
 */
final class FsPath {
    /** The root, "/", the only path with no segments. */
    static final FsPath ROOT = new FsPath(List.of());
    private final List<String> segs;
    private FsPath(List<String> segs) { this.segs = segs; }

    /** Parse and normalise a raw path. Must be absolute; everything else is cleaned up rather than rejected. */
    static FsPath of(String raw) {
        if (raw == null || !raw.startsWith("/")) throw new FsException("path must be absolute: " + raw);
        ArrayList<String> out = new ArrayList<>();
        for (String s : raw.split("/")) {
            if (s.isEmpty() || s.equals(".")) continue;
            if (s.equals("..")) { if (!out.isEmpty()) out.remove(out.size() - 1); }   // above the root clamps AT the root
            else out.add(s);
        }
        return new FsPath(List.copyOf(out));
    }

    boolean isRoot() { return segs.isEmpty(); }
    int depth() { return segs.size(); }
    String segment(int i) { return segs.get(i); }
    /** The last segment, or "" for the root. */
    String name() { return segs.isEmpty() ? "" : segs.get(segs.size() - 1); }
    /** The containing directory. The root's parent is the root. */
    FsPath parent() { return segs.isEmpty() ? ROOT : new FsPath(segs.subList(0, segs.size() - 1)); }
    /** The first n segments: prefix(2) of /a/b/c is /a/b. Used to name the exact level an error happened at. */
    FsPath prefix(int n) { return new FsPath(segs.subList(0, n)); }
    /** This path with one more segment on the end. */
    FsPath child(String name) { ArrayList<String> c = new ArrayList<>(segs); c.add(name); return new FsPath(List.copyOf(c)); }
    /** True when this path is the other one or lives underneath it. This one comparison is the move-into-own-subtree check. */
    boolean startsWith(FsPath other) {
        if (other.segs.size() > segs.size()) return false;
        return segs.subList(0, other.segs.size()).equals(other.segs);
    }
    @Override public String toString() { return segs.isEmpty() ? "/" : "/" + String.join("/", segs); }
    @Override public boolean equals(Object o) { return o instanceof FsPath p && p.segs.equals(segs); }
    @Override public int hashCode() { return segs.hashCode(); }
}

// ---------------------------------------------------------------- the tree: one base type, two shapes

/**
 * Anything a path can point at. A node knows its own name and times and can answer two questions -- are you a
 * directory, and how many bytes are underneath you. It never parses a path and never points back at the file
 * system, which is what keeps the locking story short.
 */
abstract class FsNode {
    private String name;
    private final long createdMs;
    private volatile long modifiedMs;   // written under a file's lock, read by find() without it: volatile so a reader sees a whole, current value
    FsNode(String name, long now) { this.name = name; this.createdMs = now; this.modifiedMs = now; }

    String name() { return name; }
    /** Renaming is a namespace operation, so only the file system calls this, under the namespace write lock. */
    void rename(String n) { this.name = n; }
    long createdMs() { return createdMs; }
    long modifiedMs() { return modifiedMs; }
    void touch(long now) { modifiedMs = now; }

    /** True for a directory. Asked instead of instanceof; only the path walk then casts, because only a directory has children. */
    abstract boolean isDirectory();
    /** Bytes underneath this node: its own for a file, the sum of its children for a directory. */
    abstract long sizeBytes();
}

/**
 * A file: a name and one byte array, with its own lock. The bytes are what two threads fight over, so the lock
 * that protects them lives here rather than on the file system. Methods that require the caller to hold that lock
 * say Locked in their name.
 */
final class FileNode extends FsNode {
    private final ReentrantLock lock = new ReentrantLock();
    private final AtomicLong version = new AtomicLong();
    private byte[] content = new byte[0];
    private int openHandles = 0;
    private FileState state = FileState.LIVE;

    FileNode(String name, long now) { super(name, now); }

    @Override boolean isDirectory() { return false; }
    @Override long sizeBytes() { lock.lock(); try { return content.length; } finally { lock.unlock(); } }

    void lock() { lock.lock(); }
    void unlock() { lock.unlock(); }
    /** Size while the caller already holds this file's lock. */
    long sizeLocked() { return content.length; }
    /** The live array while the caller holds the lock. Never handed outside the lock. */
    byte[] contentLocked() { return content; }
    /** Publish new bytes: one reference assignment, so it cannot fail half way. Caller holds the lock. */
    void setContentLocked(byte[] bytes, long now) { content = bytes; version.incrementAndGet(); touch(now); }
    /** A copy of the bytes, taken under the lock so a reader never sees a half-written array. */
    byte[] read() { lock.lock(); try { return content.clone(); } finally { lock.unlock(); } }
    /** Which edit this is. A caller that wants optimistic concurrency compares it (Extensions' RwFile shows the compare-and-write). */
    long version() { return version.get(); }
    FileState state() { lock.lock(); try { return state; } finally { lock.unlock(); } }

    /**
     * The same read-modify-write with NO lock. It exists only so the demo can measure what the lock buys; real
     * code goes through FileSystem.append.
     */
    void unsafeAppend(byte[] more, long now) {
        byte[] old = content;
        byte[] bigger = Arrays.copyOf(old, old.length + more.length);
        System.arraycopy(more, 0, bigger, old.length, more.length);
        content = bigger; touch(now);
    }

    /** A reader opened this file: the bytes must outlive an unlink until it closes. */
    void acquire() { lock.lock(); try { openHandles++; } finally { lock.unlock(); } }
    /** A reader closed. If the name is already gone and this was the last handle, the bytes are released now. */
    void release() {
        lock.lock();
        try { if (--openHandles == 0 && state == FileState.UNLINKED) { state = FileState.FREED; content = new byte[0]; } }
        finally { lock.unlock(); }
    }
    /** The name left the tree. LIVE goes to UNLINKED if somebody is reading, straight to FREED if nobody is. */
    void unlink() {
        lock.lock();
        try {
            if (openHandles > 0) state = FileState.UNLINKED;
            else { state = FileState.FREED; content = new byte[0]; }
        } finally { lock.unlock(); }
    }
}

/**
 * A directory: a name and its children by name. A sorted map, so ls is already in order and a lookup is
 * O(log k); a hash map would be O(1) to look up but would re-sort on every ls.
 */
final class DirNode extends FsNode {
    private final TreeMap<String, FsNode> children = new TreeMap<>();
    DirNode(String name, long now) { super(name, now); }

    @Override boolean isDirectory() { return true; }
    /** The composite: a directory's size is the sum of what is underneath it, and a child may be a directory. */
    @Override long sizeBytes() { long s = 0; for (FsNode c : children.values()) s += c.sizeBytes(); return s; }

    FsNode child(String name) { return children.get(name); }
    /** Link a node in under its own name. Caller holds the namespace write lock. */
    void put(FsNode n) { children.put(n.name(), n); }
    /** Unlink one name. Caller holds the namespace write lock. */
    FsNode remove(String name) { return children.remove(name); }
    boolean isEmpty() { return children.isEmpty(); }
    int size() { return children.size(); }
    /** Names in order. The map is already sorted, so this is a walk, not a sort. */
    List<String> names() { return new ArrayList<>(children.keySet()); }
    /** Up to n names that sort after the cursor (from the start when it is null): O(log k + n), never a copy of all k. */
    List<String> namesAfter(String after, int n) {
        List<String> out = new ArrayList<>();
        for (String s : after == null ? children.keySet() : children.tailMap(after, false).keySet()) {
            if (out.size() == n) break;
            out.add(s);
        }
        return out;
    }
    Collection<FsNode> childNodes() { return children.values(); }
}

// ---------------------------------------------------------------- the one seam on the write path

/**
 * Everything a rule could want to know about a change, computed before anything changes: the path, the kind of
 * change, the resulting size of this file, the resulting size of the whole volume, and how many files would exist.
 * A rule reads values, so a rule cannot be tempted to go and look at the tree. A tree change moves no bytes, so its
 * sizes are today's.
 */
record WriteRequest(String path, WriteMode mode, long resultingFileBytes, long resultingTotalBytes, long fileCount) {}

/**
 * The rule that decides whether a change may happen. One method, because "what is allowed" is the thing that
 * changes mid-interview: a quota, a maximum file size, a read-only subtree. Byte writes ask it, and so do mkdirs,
 * move and delete. It throws to refuse; a byte write has already reserved its bytes and releases the reservation.
 */
@FunctionalInterface
interface WriteGuard {
    /** Throw to refuse. Must be quick and must never call back into the file system: it runs inside a lock. */
    void check(WriteRequest r);
    /** The default: everything is allowed. A Null Object, so no method needs "if (guard != null)". */
    WriteGuard UNLIMITED = r -> {};
    /** Rules combine like nodes do: all of them must pass. */
    static WriteGuard allOf(WriteGuard... gs) { return r -> { for (WriteGuard g : gs) g.check(r); }; }
}

/** A size rule: no file over maxFile bytes, no volume over maxTotal bytes. The whole of "quota" in ten lines. */
final class CapacityGuard implements WriteGuard {
    private final long maxFileBytes, maxTotalBytes;
    CapacityGuard(long maxFileBytes, long maxTotalBytes) { this.maxFileBytes = maxFileBytes; this.maxTotalBytes = maxTotalBytes; }
    @Override public void check(WriteRequest r) {
        if (r.mode() != WriteMode.OVERWRITE && r.mode() != WriteMode.APPEND) return;   // mkdir, move, delete add no bytes
        if (r.resultingFileBytes() > maxFileBytes)
            throw new QuotaExceededException(r.path() + " would be " + r.resultingFileBytes() + " bytes, max is " + maxFileBytes);
        if (r.resultingTotalBytes() > maxTotalBytes)
            throw new QuotaExceededException("volume would be " + r.resultingTotalBytes() + " bytes, max is " + maxTotalBytes);
    }
}

/**
 * A guard that wraps another guard and writes down what it refused. Same interface, one extra behaviour, so it
 * can wrap a rule written next year without that rule knowing. This is the decorator on the write path.
 */
final class AuditGuard implements WriteGuard {
    private final WriteGuard inner;
    private final List<String> refused = new CopyOnWriteArrayList<>();
    AuditGuard(WriteGuard inner) { this.inner = inner; }
    @Override public void check(WriteRequest r) {
        try { inner.check(r); }
        catch (FsException e) { refused.add(r.path() + ": " + e.getMessage()); throw e; }
    }
    /** Every write this guard refused, newest last. */
    List<String> refused() { return List.copyOf(refused); }
}

// ---------------------------------------------------------------- search: one walk, many questions

/**
 * A yes/no question about one node. The traversal is written once; what changes from query to query is this
 * predicate, which is why there is no findByExtension, findBySize and findByExtensionAndSize.
 */
@FunctionalInterface
interface NodeFilter {
    boolean matches(String path, FsNode node);
    default NodeFilter and(NodeFilter o) { return (p, n) -> matches(p, n) && o.matches(p, n); }
    default NodeFilter or(NodeFilter o) { return (p, n) -> matches(p, n) || o.matches(p, n); }
    default NodeFilter negate() { return (p, n) -> !matches(p, n); }
    /** Matches everything. Useful as the start of a chain. */
    NodeFilter ANY = (p, n) -> true;
}

/** The predicates people actually ask for. Each is one line, and they combine with and / or / negate. */
final class Filters {
    static NodeFilter filesOnly() { return (p, n) -> !n.isDirectory(); }
    static NodeFilter extension(String ext) { return (p, n) -> !n.isDirectory() && n.name().endsWith("." + ext); }
    static NodeFilter largerThan(long bytes) { return (p, n) -> !n.isDirectory() && n.sizeBytes() > bytes; }
    static NodeFilter modifiedAfter(long ms) { return (p, n) -> n.modifiedMs() > ms; }
    static NodeFilter nameContains(String s) { return (p, n) -> n.name().contains(s); }
}

// ---------------------------------------------------------------- watchers: told after the unlock

/** One thing that happened: the path, where it came from (a move only, else null) and when. A value, so it can be queued or logged. */
record FsEvent(EventKind kind, String path, String from, long atMs) {
    /** Every event but a move has one path. */
    FsEvent(EventKind kind, String path, long atMs) { this(kind, path, null, atMs); }
}

/** Somebody who wants to know when a subtree changes. One method, so a test is a lambda. */
@FunctionalInterface
interface FsWatcher { void onEvent(FsEvent e); }

// ---------------------------------------------------------------- an open file

/**
 * An open file. It holds the node, not the name, which is exactly why a reader can finish reading a file that
 * somebody deleted underneath them. Read-only on purpose: writes go through the file system so the guard and the
 * byte accounting see them. Closing is what lets the bytes go.
 */
final class Handle implements AutoCloseable {
    private final String path;
    private final FileNode node;
    private final AtomicBoolean closed = new AtomicBoolean();
    Handle(String path, FileNode node) { this.path = path; this.node = node; node.acquire(); }
    /** A copy of the bytes as they are now, even if the name has already left the tree. */
    byte[] read() { if (closed.get()) throw new FsException("handle is closed: " + path); return node.read(); }
    String readString() { return new String(read(), StandardCharsets.UTF_8); }
    FileState state() { return node.state(); }
    /** Release the bytes once. compareAndSet, so two threads closing the same handle cannot release it twice. */
    @Override public void close() { if (closed.compareAndSet(false, true)) node.release(); }
}

// ---------------------------------------------------------------- the aggregate root

/**
 * The one object callers touch. It owns three things the nodes deliberately do not: what a path means, who may
 * rearrange the tree, and how many bytes exist.
 *
 * Two invariants, two locks. The SHAPE of the tree (which name points at which node) is under one
 * ReentrantReadWriteLock: mkdirs, move, delete and create take the write side; everything else takes the read
 * side. The CONTENT of a file is under that file's own lock. A byte write therefore takes the namespace READ
 * lock -- it only needs the name to stay resolved -- so writers to different files never block each other, while
 * a delete still waits for a write in flight to finish.
 *
 * The lock order is a stated rule: namespace first, then a file, never the reverse, and never two file locks at
 * once. A shape change may take a file's lock (a delete reads each file's size), but only after the namespace
 * lock, so every thread takes locks in the same order and a deadlock cannot form.
 */
final class FileSystem {
    /** One file is one byte[], and a Java array holds at most about 2^31 bytes. The chunked follow-up lifts this. */
    static final long MAX_FILE_BYTES = Integer.MAX_VALUE - 8;
    private final DirNode root;
    private final ReentrantReadWriteLock namespace = new ReentrantReadWriteLock();
    private final AtomicLong totalBytes = new AtomicLong(), fileCount = new AtomicLong();
    private volatile Clock clock = Clock.SYSTEM;
    private volatile WriteGuard guard = WriteGuard.UNLIMITED;
    private final List<Map.Entry<String, FsWatcher>> watchers = new CopyOnWriteArrayList<>();

    FileSystem() { this(Clock.SYSTEM); }
    FileSystem(Clock clock) { this.clock = clock; this.root = new DirNode("", clock.nowMs()); }

    /** Hand in the rule for the write path. The file system never builds one; the default allows everything. */
    void configure(WriteGuard guard) { this.guard = guard; }
    /** Hand in time. A test passes a clock that returns whatever instant it likes. */
    void setClock(Clock c) { this.clock = c; }
    /**
     * Tell this watcher about anything that happens at or under prefix -- including a move out of it, and the delete
     * or move of a folder above it. Called after the unlock, never inside it.
     */
    void watch(String prefix, FsWatcher w) { watchers.add(Map.entry(FsPath.of(prefix).toString(), w)); }

    // ------------------------------------------------ shape: the write side of the namespace lock

    /**
     * mkdir -p: create every missing level and return quietly if it is all already there. Refuses when a level on
     * the way is a file (a file cannot have children) and when the path itself is a file. The guard is asked once,
     * before the first level is made, so a refusal leaves nothing half-built.
     */
    void mkdirs(String path) {
        FsPath p = FsPath.of(path);
        boolean made = false;
        namespace.writeLock().lock();
        try {
            DirNode cur = root;
            for (int i = 0; i < p.depth(); i++) {
                String seg = p.segment(i);
                FsNode next = cur.child(seg);
                if (next == null) {
                    if (!made) guard.check(shapeChange(p, WriteMode.MKDIR));
                    DirNode fresh = new DirNode(seg, clock.nowMs()); cur.put(fresh); next = fresh; made = true;
                } else if (!next.isDirectory()) {
                    if (i == p.depth() - 1) throw new AlreadyExistsException(p.toString());   // the path itself is a file
                    throw new NotADirectoryException(p.prefix(i + 1).toString());           // name the file in the way
                }
                cur = (DirNode) next;
            }
        } finally { namespace.writeLock().unlock(); }
        if (made) publish(new FsEvent(EventKind.CREATED, p.toString(), clock.nowMs()));   // a no-op mkdir -p is not an event
    }

    /** mkdir without -p (Coinbase's and LeetCode 1166's rule): exactly one new level, or an error if the parent is missing or the name is taken. */
    void mkdir(String path) {
        FsPath p = FsPath.of(path);
        if (p.isRoot()) throw new AlreadyExistsException("/");
        namespace.writeLock().lock();
        try {
            DirNode parent = dirAt(p.parent());                             // NotFoundException if the parent is missing
            if (parent.child(p.name()) != null) throw new AlreadyExistsException(p.toString());
            guard.check(shapeChange(p, WriteMode.MKDIR));
            parent.put(new DirNode(p.name(), clock.nowMs()));
        } finally { namespace.writeLock().unlock(); }
        publish(new FsEvent(EventKind.CREATED, p.toString(), clock.nowMs()));
    }

    /** Create the file or replace its bytes. */
    void putFile(String path, String content) { createOrWrite(path, content, WriteMode.OVERWRITE); }

    /** LeetCode 588's addContentToFile: create the file, or add to its end if it exists -- one step, so two first writers cannot wipe each other. */
    void addContent(String path, String content) { createOrWrite(path, content, WriteMode.APPEND); }

    /**
     * The create path. It may change the shape of the tree, so it takes the write side. The order is the whole
     * point: resolve, reserve the bytes, ask the guard, and only then create the node -- so a refused write has
     * nothing to roll back, because nothing was ever linked in.
     */
    private void createOrWrite(String path, String content, WriteMode mode) {
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        FsPath p = FsPath.of(path);
        if (p.isRoot()) throw new IsADirectoryException("/");
        EventKind kind;
        namespace.writeLock().lock();
        try {
            DirNode parent = dirAt(p.parent());
            FsNode existing = parent.child(p.name());
            if (existing != null && existing.isDirectory()) throw new IsADirectoryException(path);
            FileNode f = (FileNode) existing;
            long before = f == null ? 0 : f.sizeBytes();
            long after = mode == WriteMode.APPEND ? before + bytes.length : bytes.length;
            if (after > MAX_FILE_BYTES) throw new QuotaExceededException(path + " would pass 2 GB, the most one byte[] can hold");
            long delta = after - before;
            long total = totalBytes.addAndGet(delta);                       // reserve first: a number moves, no bytes yet
            long count = f == null ? fileCount.get() + 1 : fileCount.get();
            try { guard.check(new WriteRequest(p.toString(), mode, after, total, count)); }
            catch (RuntimeException e) { totalBytes.addAndGet(-delta); throw e; }   // release the reservation; nothing was created
            if (f == null) { f = new FileNode(p.name(), clock.nowMs()); parent.put(f); fileCount.incrementAndGet(); kind = EventKind.CREATED; }
            else kind = EventKind.WRITTEN;
            f.lock();
            try { f.setContentLocked(mode == WriteMode.APPEND ? concat(f.contentLocked(), bytes) : bytes, clock.nowMs()); }
            finally { f.unlock(); }
        } finally { namespace.writeLock().unlock(); }
        publish(new FsEvent(kind, p.toString(), clock.nowMs()));
    }

    /**
     * Rename or move a node. Three pointer operations regardless of how big the subtree is: unlink the old name,
     * rename the node, link the new name -- all inside one exclusive lock, so nobody can observe the moment when
     * the node is at neither name. Refuses a move into the mover's own subtree, which would orphan it.
     */
    void move(String from, String to) {
        FsPath src = FsPath.of(from), dst = FsPath.of(to);
        if (src.isRoot() || dst.isRoot()) throw new InvalidMoveException("cannot move the root");
        namespace.writeLock().lock();
        try {
            DirNode srcParent = dirAt(src.parent());
            FsNode node = srcParent.child(src.name());
            if (node == null) throw new NotFoundException(from);
            if (src.equals(dst)) return;                                    // it exists, and a move onto itself changes nothing
            if (node.isDirectory() && dst.startsWith(src))
                throw new InvalidMoveException("cannot move " + src + " into its own subtree " + dst);
            DirNode dstParent = dirAt(dst.parent());
            if (dstParent.child(dst.name()) != null) throw new AlreadyExistsException(to);
            guard.check(shapeChange(src, WriteMode.MOVE));                  // the name leaves here...
            guard.check(shapeChange(dst, WriteMode.MOVE));                  // ...and arrives here: both must be allowed
            srcParent.remove(src.name());
            node.rename(dst.name());
            dstParent.put(node);
            node.touch(clock.nowMs());
        } finally { namespace.writeLock().unlock(); }
        publish(new FsEvent(EventKind.MOVED, dst.toString(), src.toString(), clock.nowMs()));
    }

    /**
     * Delete a file, or a directory that recursive says may take its children with it. The name leaves the tree
     * inside the lock; the bytes of any file somebody still has open survive until that reader closes.
     */
    void delete(String path, boolean recursive) {
        FsPath p = FsPath.of(path);
        if (p.isRoot()) throw new InvalidMoveException("cannot delete the root");
        List<FileNode> orphans = new ArrayList<>();
        namespace.writeLock().lock();
        try {
            DirNode parent = dirAt(p.parent());
            FsNode node = parent.child(p.name());
            if (node == null) throw new NotFoundException(path);
            if (node.isDirectory() && !((DirNode) node).isEmpty() && !recursive) throw new DirectoryNotEmptyException(path);
            guard.check(shapeChange(p, WriteMode.DELETE));
            collect(node, orphans);
            parent.remove(p.name());                                        // one pointer op; the subtree leaves with it
            long bytes = 0;
            for (FileNode f : orphans) bytes += f.sizeBytes();
            totalBytes.addAndGet(-bytes);
            fileCount.addAndGet(-orphans.size());
        } finally { namespace.writeLock().unlock(); }
        for (FileNode f : orphans) f.unlink();                              // LIVE -> UNLINKED, or straight to FREED
        publish(new FsEvent(EventKind.DELETED, p.toString(), clock.nowMs()));
    }

    // ------------------------------------------------ content: the read side plus the file's own lock

    /** Replace the bytes of a file that already exists. No shape change, so only the read side of the namespace lock. */
    void overwrite(String path, String content) { applyWrite(path, content.getBytes(StandardCharsets.UTF_8), WriteMode.OVERWRITE); }

    /** Add to the end of a file that already exists. The operation two threads can lose, which is why it is locked. */
    void append(String path, String more) { applyWrite(path, more.getBytes(StandardCharsets.UTF_8), WriteMode.APPEND); }

    /**
     * The one guarded step every byte write funnels through. In order: hold the name still (namespace read lock),
     * take the file's lock, work out the resulting sizes, reserve them on the volume counter, ask the guard, and
     * only then publish the new array -- one reference assignment, which cannot fail half way. A refused write
     * releases its reservation and leaves the old bytes exactly where they were.
     */
    private void applyWrite(String path, byte[] bytes, WriteMode mode) {
        FsPath p = FsPath.of(path);
        namespace.readLock().lock();
        try {
            FsNode n = nodeAt(p);
            if (n.isDirectory()) throw new IsADirectoryException(path);
            FileNode f = (FileNode) n;
            f.lock();                                                       // order: namespace, then file. Never the reverse.
            try {
                long before = f.sizeLocked();
                long after = mode == WriteMode.APPEND ? before + bytes.length : bytes.length;
                if (after > MAX_FILE_BYTES) throw new QuotaExceededException(path + " would pass 2 GB, the most one byte[] can hold");
                long delta = after - before;
                long total = totalBytes.addAndGet(delta);                   // reserve, so two writers cannot both pass one quota
                try { guard.check(new WriteRequest(p.toString(), mode, after, total, fileCount.get())); }
                catch (RuntimeException e) { totalBytes.addAndGet(-delta); throw e; }
                f.setContentLocked(mode == WriteMode.APPEND ? concat(f.contentLocked(), bytes) : bytes.clone(), clock.nowMs());
            } finally { f.unlock(); }
        } finally { namespace.readLock().unlock(); }
        publish(new FsEvent(EventKind.WRITTEN, p.toString(), clock.nowMs()));
    }

    // ------------------------------------------------ reads

    /** The whole file, as bytes. */
    byte[] read(String path) {
        namespace.readLock().lock();
        try {
            FsNode n = nodeAt(FsPath.of(path));
            if (n.isDirectory()) throw new IsADirectoryException(path);
            return ((FileNode) n).read();
        } finally { namespace.readLock().unlock(); }
    }

    /** The whole file, as text. The demo's convenience; the core is bytes. */
    String readString(String path) { return new String(read(path), StandardCharsets.UTF_8); }

    /** Child names in order. The children map is already sorted, so this is a walk and not a sort. */
    List<String> ls(String path) {
        namespace.readLock().lock();
        try {
            FsNode n = nodeAt(FsPath.of(path));
            if (!n.isDirectory()) return List.of(n.name());
            return ((DirNode) n).names();
        } finally { namespace.readLock().unlock(); }
    }

    /** One page of a big directory: up to limit names after the cursor, O(log k + limit), not a copy of all k names. */
    List<String> ls(String path, String after, int limit) {
        namespace.readLock().lock();
        try {
            FsNode n = nodeAt(FsPath.of(path));
            if (!n.isDirectory()) throw new NotADirectoryException(path);
            return ((DirNode) n).namesAfter(after, limit);
        } finally { namespace.readLock().unlock(); }
    }

    /** Bytes underneath a path, computed by walking it. The O(1) answer for the whole volume is totalBytes(). */
    long du(String path) {
        namespace.readLock().lock();
        try { return nodeAt(FsPath.of(path)).sizeBytes(); } finally { namespace.readLock().unlock(); }
    }

    /** True when something lives at that path. */
    boolean exists(String path) {
        namespace.readLock().lock();
        try { nodeAt(FsPath.of(path)); return true; } catch (FsException e) { return false; }
        finally { namespace.readLock().unlock(); }
    }

    /** True when a directory lives at that path. */
    boolean isDirectory(String path) {
        namespace.readLock().lock();
        try { return nodeAt(FsPath.of(path)).isDirectory(); } catch (FsException e) { return false; }
        finally { namespace.readLock().unlock(); }
    }

    /** Every path at or under from whose node answers yes to the filter. One walk, any question. */
    List<String> find(String from, NodeFilter filter) {
        FsPath start = FsPath.of(from);
        List<String> out = new ArrayList<>();
        namespace.readLock().lock();
        try { walk(start, nodeAt(start), filter, out); } finally { namespace.readLock().unlock(); }
        return out;
    }

    /** Open a file for reading. The handle keeps the bytes alive even if the name is deleted while it is open. */
    Handle open(String path) {
        namespace.readLock().lock();
        try {
            FsNode n = nodeAt(FsPath.of(path));
            if (n.isDirectory()) throw new IsADirectoryException(path);
            return new Handle(path, (FileNode) n);
        } finally { namespace.readLock().unlock(); }
    }

    /** Bytes reachable by name, kept incrementally so a quota check is O(1) instead of a walk of the tree. */
    long totalBytes() { return totalBytes.get(); }
    /** Files reachable by name, kept the same way. */
    long fileCount() { return fileCount.get(); }

    /** The node at a path. Exposed only for the demo's unlocked-append race, which needs to bypass the lock on purpose. */
    FileNode fileNodeAt(String path) {
        namespace.readLock().lock();
        try {
            FsNode n = nodeAt(FsPath.of(path));
            if (n.isDirectory()) throw new IsADirectoryException(path);
            return (FileNode) n;
        } finally { namespace.readLock().unlock(); }
    }

    // ------------------------------------------------ the private walk

    /** Resolve a path to its node. O(depth x log children). Caller holds at least the namespace read lock. */
    private FsNode nodeAt(FsPath p) {
        FsNode cur = root;
        for (int i = 0; i < p.depth(); i++) {
            if (!cur.isDirectory()) throw new NotADirectoryException(p.toString());
            FsNode next = ((DirNode) cur).child(p.segment(i));
            if (next == null) throw new NotFoundException(p.toString());
            cur = next;
        }
        return cur;
    }

    /** Resolve a path that must be a directory. */
    private DirNode dirAt(FsPath p) {
        FsNode n = nodeAt(p);
        if (!n.isDirectory()) throw new NotADirectoryException(p.toString());
        return (DirNode) n;
    }

    /** Depth-first walk, collecting the paths whose node matches. Caller holds the read lock, so the tree is still. */
    private void walk(FsPath path, FsNode node, NodeFilter filter, List<String> out) {
        if (filter.matches(path.toString(), node)) out.add(path.toString());
        if (node.isDirectory()) for (FsNode c : ((DirNode) node).childNodes()) walk(path.child(c.name()), c, filter, out);
    }

    /** Every file underneath a node, so a delete can unlink them all and correct the accounting once. */
    private void collect(FsNode node, List<FileNode> out) {
        if (!node.isDirectory()) { out.add((FileNode) node); return; }
        for (FsNode c : ((DirNode) node).childNodes()) collect(c, out);
    }

    /** The old bytes followed by the new ones, in a fresh array: the shape of every append. */
    private static byte[] concat(byte[] old, byte[] more) {
        byte[] out = Arrays.copyOf(old, old.length + more.length);
        System.arraycopy(more, 0, out, old.length, more.length);
        return out;
    }

    /** What the guard is shown for a mkdir, move or delete: the path and the kind; no bytes move, so the sizes are today's. */
    private WriteRequest shapeChange(FsPath p, WriteMode mode) {
        return new WriteRequest(p.toString(), mode, 0, totalBytes.get(), fileCount.get());
    }

    /**
     * Tell the watchers, after every lock is released and inside a try/catch. A watcher that throws is a broken
     * watcher, not a failed write.
     */
    private void publish(FsEvent e) {
        for (Map.Entry<String, FsWatcher> w : watchers) {
            if (!concerns(FsPath.of(w.getKey()), e)) continue;
            try { w.getValue().onEvent(e); } catch (RuntimeException ignored) { /* log it; never fail the write */ }
        }
    }

    /**
     * Does this event matter to a watcher on this folder? Yes if it happened at or under the folder, if a move took
     * something out of it, or if a delete or move took away a folder above it (the watched folder went too).
     */
    private static boolean concerns(FsPath watched, FsEvent e) {
        FsPath at = FsPath.of(e.path()), from = e.from() == null ? null : FsPath.of(e.from());
        if (at.startsWith(watched) || (from != null && from.startsWith(watched))) return true;
        FsPath gone = from != null ? from : (e.kind() == EventKind.DELETED ? at : null);
        return gone != null && watched.startsWith(gone);
    }
}

// ---------------------------------------------------------------- the demo, and the race

/** Runs the whole system: a demo of every flow, then the two races this design claims to win. */
public class Main {

    /** Eight threads, each appending one byte five hundred times, released together by a latch. Returns the final size. */
    static long hammer(FileSystem fs, String path, boolean locked) throws Exception {
        fs.putFile(path, "");
        FileNode node = fs.fileNodeAt(path);
        CountDownLatch go = new CountDownLatch(1), done = new CountDownLatch(8);
        ExecutorService pool = Executors.newFixedThreadPool(8);
        for (int t = 0; t < 8; t++) {
            pool.submit(() -> {
                try {
                    go.await();
                    for (int i = 0; i < 500; i++) {
                        if (locked) fs.append(path, "x");
                        else node.unsafeAppend("x".getBytes(StandardCharsets.UTF_8), 0);
                    }
                } catch (Exception ignored) { } finally { done.countDown(); }
            });
        }
        go.countDown();
        done.await();
        pool.shutdown();
        return fs.read(path).length;
    }

    public static void main(String[] args) throws Exception {
        FileSystem fs = new FileSystem();

        // --- the basic flows
        fs.mkdirs("/home/harish/notes");
        fs.putFile("/home/harish/notes/todo.txt", "buy milk");
        fs.append("/home/harish/notes/todo.txt", "\nfix the lock");
        System.out.println("todo.txt -> " + fs.readString("/home/harish/notes/todo.txt").replace("\n", " / "));
        System.out.println("ls /home/harish -> " + fs.ls("/home/harish") + "   du / = " + fs.du("/") + " bytes");

        // --- the path is normalised once: "." and ".." never reach a method
        System.out.println("a path with .. resolves: " + fs.readString("/home/harish/notes/../notes/./todo.txt").startsWith("buy"));
        System.out.println("\"/a/../../..\" clamps at the root: " + FsPath.of("/a/../../.."));

        // --- move is three pointer operations, whatever the subtree weighs
        fs.mkdirs("/home/harish/notes/2026/september");
        fs.putFile("/home/harish/notes/2026/september/plan.md", "ship the workbench");
        fs.move("/home/harish/notes", "/home/harish/archive");
        System.out.println("after moving the whole subtree: " + fs.readString("/home/harish/archive/2026/september/plan.md"));
        try { fs.move("/home/harish/archive", "/home/harish/archive/2026/copy"); }
        catch (InvalidMoveException e) { System.out.println("expected: " + e.getMessage()); }

        // --- rm is loud about a non-empty directory
        try { fs.delete("/home/harish/archive/2026", false); }
        catch (DirectoryNotEmptyException e) { System.out.println("expected: " + e.getMessage()); }

        // --- one rule, handed in: no file over 64 bytes, no volume over 1 KB, and every refusal recorded
        AuditGuard audit = new AuditGuard(WriteGuard.allOf(new CapacityGuard(64, 1024)));
        fs.configure(audit);
        long bytesBefore = fs.totalBytes(), filesBefore = fs.fileCount();
        try { fs.putFile("/home/harish/big.bin", "z".repeat(200)); }
        catch (QuotaExceededException e) { System.out.println("expected: " + e.getMessage()); }
        System.out.println("after the refused write: bytes " + bytesBefore + " -> " + fs.totalBytes()
            + ", files " + filesBefore + " -> " + fs.fileCount() + ", exists=" + fs.exists("/home/harish/big.bin"));
        System.out.println("the audit guard recorded: " + audit.refused());
        fs.configure(WriteGuard.UNLIMITED);

        // --- watchers hear after the unlock, and a broken watcher cannot break a write
        List<FsEvent> seen = new CopyOnWriteArrayList<>();
        fs.watch("/home", seen::add);
        fs.watch("/home", e -> { throw new IllegalStateException("this watcher is broken"); });
        fs.putFile("/home/harish/hello.txt", "hi");
        System.out.println("the watcher saw " + seen.get(seen.size() - 1) + " and the broken one changed nothing");

        // --- one walk, any question
        fs.putFile("/home/harish/archive/big.txt", "x".repeat(50));
        System.out.println("find *.txt over 8 bytes under /home -> "
            + fs.find("/home", Filters.extension("txt").and(Filters.largerThan(8))));

        // --- an open handle keeps the bytes alive after the name is gone
        try (Handle h = fs.open("/home/harish/hello.txt")) {
            fs.delete("/home/harish/hello.txt", false);
            System.out.println("deleted while open: name gone=" + !fs.exists("/home/harish/hello.txt")
                + ", the reader still gets \"" + h.readString() + "\", state=" + h.state());
        }

        // --- race 1: eight threads x 500 one-byte appends to ONE file, on a file system of its own
        // (the unlocked path deliberately writes bytes behind the accounting's back, so it gets its own volume)
        FileSystem raceFs = new FileSystem();
        long unlocked = hammer(raceFs, "/race-unlocked.txt", false);
        long locked = hammer(raceFs, "/race-locked.txt", true);
        System.out.println("8 threads x 500 appends -- unlocked: " + unlocked + "/4000 bytes ("
            + (4000 - unlocked) + " lost), locked: " + locked + "/4000 bytes");
        if (locked != 4000) throw new AssertionError("the file lock lost an append");

        // --- race 2: fifty threads creating fifty files in ONE directory at the same instant (FailureTests 7 adds two on one name)
        fs.mkdirs("/tmp/burst");
        CountDownLatch go = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        List<Future<?>> jobs = new ArrayList<>();
        for (int i = 0; i < 50; i++) {
            final int n = i;
            jobs.add(pool.submit(() -> { go.await(); fs.putFile("/tmp/burst/f" + n + ".txt", "n" + n); return null; }));
        }
        go.countDown();
        for (Future<?> f : jobs) f.get();
        pool.shutdown();
        System.out.println("50 threads created " + fs.ls("/tmp/burst").size() + " files in one directory (must be 50)");
        if (fs.ls("/tmp/burst").size() != 50) throw new AssertionError("a create was lost");

        // --- the accounting is incremental, and it must still agree with a fresh walk of the tree
        System.out.println("running total " + fs.totalBytes() + " == du(\"/\") " + fs.du("/"));
        if (fs.totalBytes() != fs.du("/")) throw new AssertionError("the accounting drifted");
    }
}
