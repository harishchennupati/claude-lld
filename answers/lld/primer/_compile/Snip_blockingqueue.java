import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_blockingqueue {
java.util.concurrent.BlockingQueue<String> q = new java.util.concurrent.ArrayBlockingQueue<>(1000);
static final String POISON = "__stop__";
void producer(java.util.List<String> jobs) throws InterruptedException {
    for (String j : jobs) q.put(j);                  // blocks when 1000 are waiting: back-pressure
    q.put(POISON);
}
void consumer() throws InterruptedException {
    while (true) {
        String j = q.take();                          // blocks when empty, no spinning
        if (j.equals(POISON)) return;
        process(j);
    }
}
void process(String j) {}
}
