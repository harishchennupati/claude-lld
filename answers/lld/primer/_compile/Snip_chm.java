import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_chm {
java.util.concurrent.ConcurrentHashMap<String, java.util.concurrent.locks.ReentrantLock> locks = new java.util.concurrent.ConcurrentHashMap<>();
java.util.concurrent.locks.ReentrantLock lockFor(String key) {
    return locks.computeIfAbsent(key, k -> new java.util.concurrent.locks.ReentrantLock());   // per-key lock, striped by key
}
java.util.concurrent.ConcurrentHashMap<String, Integer> hits = new java.util.concurrent.ConcurrentHashMap<>();
void hit(String url) { hits.merge(url, 1, Integer::sum); }                      // atomic counter per key
java.util.concurrent.ConcurrentHashMap<String, String> claims = new java.util.concurrent.ConcurrentHashMap<>();
boolean claim(String seat, String user) { return claims.putIfAbsent(seat, user) == null; }   // first writer wins
}
