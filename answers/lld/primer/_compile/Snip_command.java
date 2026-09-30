import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_command {
interface Command { void execute(); void undo(); }
static class Editor { final StringBuilder text = new StringBuilder(); }
static class Insert implements Command {
    private final Editor ed; private final int at; private final String s;
    Insert(Editor ed, int at, String s) { this.ed = ed; this.at = at; this.s = s; }
    public void execute() { ed.text.insert(at, s); }
    public void undo() { ed.text.delete(at, at + s.length()); }
}
static class History {
    private final java.util.Deque<Command> done = new java.util.ArrayDeque<>(), undone = new java.util.ArrayDeque<>();
    void run(Command c) { c.execute(); done.push(c); undone.clear(); }
    void undo() { if (!done.isEmpty()) { Command c = done.pop(); c.undo(); undone.push(c); } }
    void redo() { if (!undone.isEmpty()) { Command c = undone.pop(); c.execute(); done.push(c); } }
}
}
