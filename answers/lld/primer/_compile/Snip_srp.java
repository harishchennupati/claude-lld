import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_srp {
// BEFORE: one class, four reasons to change
static class OrderServiceBefore {
    void place(String order) { /* validate */ /* price */ /* save to db */ /* send email */ }
}
// AFTER: each concern is its own class; the service only orchestrates
interface Validator { void validate(String o); }
interface Pricer { long price(String o); }
interface OrderRepo { void save(String o, long price); }
interface Notifier { void placed(String o); }
static class OrderService {
    private final Validator v; private final Pricer p; private final OrderRepo r; private final Notifier n;
    OrderService(Validator v, Pricer p, OrderRepo r, Notifier n) { this.v = v; this.p = p; this.r = r; this.n = n; }
    void place(String o) { v.validate(o); long price = p.price(o); r.save(o, price); n.placed(o); }
}
}
