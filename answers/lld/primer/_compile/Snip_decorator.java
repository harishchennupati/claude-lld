import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_decorator {
interface Pricing { double price(long minutes); }
static class Flat implements Pricing { public double price(long m) { return Math.ceil(m / 60.0) * 20; } }
static class Surge implements Pricing {                       // wraps, does not replace
    private final Pricing base; private final double factor;
    Surge(Pricing base, double factor) { this.base = base; this.factor = factor; }
    public double price(long m) { return base.price(m) * factor; }
}
static class Capped implements Pricing {
    private final Pricing base; private final double cap;
    Capped(Pricing base, double cap) { this.base = base; this.cap = cap; }
    public double price(long m) { return Math.min(cap, base.price(m)); }
}
Pricing weekend = new Capped(new Surge(new Flat(), 1.5), 500);   // stacks: cap(surge(flat))
}
