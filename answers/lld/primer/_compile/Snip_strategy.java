import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_strategy {
interface EvictionPolicy<K> { K victim(java.util.Collection<K> keys); }
static class EvictLru<K> implements EvictionPolicy<K> { public K victim(java.util.Collection<K> keys) { return keys.iterator().next(); } }
static class Cache<K, V> {
    private final java.util.Map<K, V> map = new java.util.LinkedHashMap<>();
    private final EvictionPolicy<K> policy; private final int cap;
    Cache(int cap, EvictionPolicy<K> policy) { this.cap = cap; this.policy = policy; }   // injected
    void put(K k, V v) { if (map.size() >= cap && !map.containsKey(k)) map.remove(policy.victim(map.keySet())); map.put(k, v); }
}
}
