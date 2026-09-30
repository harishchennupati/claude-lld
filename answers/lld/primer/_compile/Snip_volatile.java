import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_volatile {
static class Worker implements Runnable {
    private volatile boolean running = true;         // flag: one writer, many readers
    public void run() { while (running) { /* work */ } }
    void stop() { running = false; }                 // seen by run() promptly
}
static class BrokenCounter {
    private volatile int n;
    void inc() { n++; }                              // WRONG under contention: lost updates
}
}
