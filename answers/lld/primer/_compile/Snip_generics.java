import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_generics {
interface Repository<T, ID> {
    java.util.Optional<T> findById(ID id);
    void save(T entity);
}
static class InMemoryRepo<T, ID> implements Repository<T, ID> {
    private final java.util.Map<ID, T> store = new java.util.concurrent.ConcurrentHashMap<>();
    private final java.util.function.Function<T, ID> idOf;
    InMemoryRepo(java.util.function.Function<T, ID> idOf) { this.idOf = idOf; }
    public java.util.Optional<T> findById(ID id) { return java.util.Optional.ofNullable(store.get(id)); }
    public void save(T e) { store.put(idOf.apply(e), e); }
}
static <T extends Comparable<T>> T max(java.util.List<? extends T> xs) {
    T best = xs.get(0);
    for (T x : xs) if (x.compareTo(best) > 0) best = x;
    return best;
}
}
