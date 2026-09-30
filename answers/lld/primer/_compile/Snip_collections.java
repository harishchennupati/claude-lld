import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_collections {
java.util.Deque<Integer> stack = new java.util.ArrayDeque<>();     // push/pop/peek; also offer/poll for FIFO
java.util.TreeMap<Integer, Integer> book = new java.util.TreeMap<>();  // book.floorKey(x), book.firstEntry(), headMap(x)
java.util.PriorityQueue<int[]> byDist = new java.util.PriorityQueue<>((a, b) -> Integer.compare(a[1], b[1]));
static class LruCache<K, V> extends java.util.LinkedHashMap<K, V> {
    private final int cap;
    LruCache(int cap) { super(16, 0.75f, true); this.cap = cap; }        // accessOrder = true
    @Override protected boolean removeEldestEntry(java.util.Map.Entry<K, V> e) { return size() > cap; }
}
}
