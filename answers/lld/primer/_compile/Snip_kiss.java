import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_kiss {
// YAGNI: one pricing rule today -> a method, not a Strategy hierarchy
static class Lot1 { double price(long minutes) { return Math.ceil(minutes / 60.0) * 20; } }
// the moment a second rule is asked for -> now the interface earns its place
interface Pricing { double price(long minutes); }
static class Lot2 { private final Pricing p; Lot2(Pricing p) { this.p = p; } double price(long m) { return p.price(m); } }
}
