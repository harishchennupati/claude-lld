import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_synchronized {
static class Counter {
    private int n;                                   // guarded by this
    synchronized void inc() { n++; }                 // read-modify-write is 3 ops; the lock makes it one
    synchronized int get() { return n; }             // reads need the lock too, for visibility
}
static class Account {
    private final Object lock = new Object();        // private lock: callers cannot deadlock you
    private long balance;
    void deposit(long amt) { synchronized (lock) { balance += amt; } }
}
}
