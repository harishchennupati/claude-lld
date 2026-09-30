import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_singleton {
enum Registry { INSTANCE; final java.util.Map<String, String> m = new java.util.concurrent.ConcurrentHashMap<>(); }
static class Pool {
    private Pool() {}
    private static class Holder { static final Pool INSTANCE = new Pool(); }   // lazy, thread-safe by class-init rules
    static Pool get() { return Holder.INSTANCE; }
}
static class Service {
    private final Pool pool;
    Service(Pool pool) { this.pool = pool; }              // injected -- tests pass a fake
}
}
