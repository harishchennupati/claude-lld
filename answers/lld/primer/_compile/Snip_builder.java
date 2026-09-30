import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_builder {
static final class Request {
    final String url, method; final java.util.Map<String, String> headers; final int timeoutMs;
    private Request(Builder b) { url = b.url; method = b.method; headers = java.util.Map.copyOf(b.headers); timeoutMs = b.timeoutMs; }
    static Builder to(String url) { return new Builder(url); }
    static final class Builder {
        private final String url; private String method = "GET"; private int timeoutMs = 1000;
        private final java.util.Map<String, String> headers = new java.util.HashMap<>();
        Builder(String url) { this.url = url; }
        Builder method(String m) { method = m; return this; }
        Builder header(String k, String v) { headers.put(k, v); return this; }
        Builder timeout(int ms) { timeoutMs = ms; return this; }
        Request build() { if (timeoutMs <= 0) throw new IllegalStateException("timeout"); return new Request(this); }
    }
}
Request r = Request.to("/x").method("POST").header("a", "b").timeout(500).build();
}
