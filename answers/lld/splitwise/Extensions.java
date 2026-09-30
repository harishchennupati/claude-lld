import java.util.*;
import java.util.concurrent.*;

// Reference code for every follow-up on page 05. Each block is one twist, and each is small on purpose:
// a twist that needs a big block means the derivation on page 02 went wrong.

// ---- ext: a fourth way to split -- by shares, 2:1:1. A NEW class and one registry line; nothing else moves.
/**
 * Weights: a couple sharing a room pays two units, a single pays one. The last participant absorbs the rounding
 * so the shares still sum to the bill to the paise; CheckedSplit would catch it if they did not.
 */
class SharesSplit implements SplitStrategy {
    public List<Share> split(long total, String payerId, List<Participant> parts) {
        long units = 0;
        for (Participant p : parts) {
            if (p.rawValue() <= 0) throw new IllegalArgumentException("a weight must be positive: " + p.userId());
            units += p.rawValue();
        }
        List<Share> out = new ArrayList<>(parts.size());
        long allocated = 0;
        for (int i = 0; i < parts.size(); i++) {
            long paise = (i == parts.size() - 1) ? total - allocated            // the last one absorbs the drift
                                                 : total * parts.get(i).rawValue() / units;
            allocated += paise;
            out.add(new Share(parts.get(i).userId(), paise));
        }
        return out;
    }
}
// the only change at the call site:
//   group.configure(Map.of(EQUAL, new EqualSplit(), EXACT, new ExactSplit(),
//                          PERCENT, new PercentSplit(), SHARES, new SharesSplit()), new MinCashFlow());
// the one seam that is not free: SplitType is an enum, so a new type costs one constant. Key the
// registry by String and even that disappears.

// ---- ext: fairness -- rotate who absorbs the odd paise, instead of the same person always winning them
/**
 * Same equal split, but the extra paise start from a different participant each time, chosen by a counter kept
 * inside the rule. Over many expenses everyone absorbs the same number of stray paise.
 */
class RotatingRemainderSplit implements SplitStrategy {
    private final java.util.concurrent.atomic.AtomicLong seq = new java.util.concurrent.atomic.AtomicLong();
    public List<Share> split(long total, String payerId, List<Participant> parts) {
        int n = parts.size();
        long base = total / n, extra = total - base * n;
        int start = (int) Math.floorMod(seq.getAndIncrement(), n);              // rotate the starting point
        Map<String, Long> byUser = new HashMap<>();
        for (Participant p : parts) byUser.put(p.userId(), base);
        for (int i = 0; i < extra; i++) byUser.merge(parts.get((start + i) % n).userId(), 1L, Long::sum);
        List<Share> out = new ArrayList<>(n);
        for (Participant p : parts) out.add(new Share(p.userId(), byUser.get(p.userId())));
        return out;
    }
}

// ---- ext: multi-currency -- money grows a currency, one ledger per currency, FX only at settle time
/** An amount with a currency. The minor unit is still an integer: 12345 INR is 123.45 rupees. */
record Amount(String currency, long minor) {}

/** Today's rate, handed in. Injected so a settlement can be priced at a rate a test controls. */
interface FxRates { long convert(long minor, String from, String to); }

/**
 * One ledger per currency, so a euro debt is never silently added to a rupee debt. Balances are never re-priced
 * when the rate moves: the conversion happens once, at the moment somebody actually settles. Like Ledger it has
 * no lock of its own: the group calls it inside the group's lock.
 */
class MultiCurrencyLedger {
    private final Map<String, Ledger> byCurrency = new HashMap<>();
    /** Apply an expense in its own currency. */
    void apply(String currency, String payerId, List<Share> shares, int sign) {
        byCurrency.computeIfAbsent(currency, c -> new Ledger()).apply(payerId, shares, sign);
    }
    /** What this person's net is in one currency. */
    long netOf(String currency, String userId) {
        Ledger l = byCurrency.get(currency);
        return l == null ? 0 : l.netOf(userId);
    }
    /** A single figure for a screen: every currency converted into one, at today's rate, for display only. */
    long netIn(String display, String userId, FxRates fx) {
        long total = 0;
        for (Map.Entry<String, Ledger> e : byCurrency.entrySet())
            total += fx.convert(e.getValue().netOf(userId), e.getKey(), display);
        return total;
    }
}

// ---- ext: an expense between two friends with no group -- the pair IS a group of two
/**
 * Splitwise has no separate "friend expense" model and neither do we: a pair is a group of two with an id built
 * from the two user ids in sorted order, so alice-bob and bob-alice are the same group, created once.
 */
class Friends {
    /**
     * The two-person group for this pair, created on first use. Same lock, same ledger, same code path. "Look it up,
     * and create it if missing" as two steps would let both friends create one at the same moment and lose an
     * expense; groupOrCreate is one atomic step (computeIfAbsent).
     */
    static Group between(Splitwise app, String a, String b) {
        String id = a.compareTo(b) < 0 ? "pair:" + a + ":" + b : "pair:" + b + ":" + a;
        return app.groupOrCreate(id, a, b);
    }
}

// ---- ext: recurring expenses -- a schedule, and a deterministic id so a replay cannot double-charge
/**
 * The rent, every month. due() returns the expense ids that should exist by now; the id contains the period, so
 * running the job twice, or running it on two servers, posts each month exactly once (addExpense is idempotent).
 */
class Recurring {
    private final String template, payerId; private final long amountPaise, everyMs, startMs;
    private final List<Participant> parts;
    Recurring(String template, String payerId, long amountPaise, List<Participant> parts, long startMs, long everyMs) {
        if (everyMs <= 0) throw new IllegalArgumentException("the period must be positive, or post() never ends");
        this.template = template; this.payerId = payerId; this.amountPaise = amountPaise;
        this.parts = List.copyOf(parts); this.startMs = startMs; this.everyMs = everyMs;
    }
    /** Post every period that has arrived by nowMs. Safe to call as often as you like. */
    List<Expense> post(Group g, long nowMs) {
        List<Expense> out = new ArrayList<>();
        for (long period = 0; startMs + period * everyMs <= nowMs; period++)
            out.add(g.addExpense(template + "#" + period, payerId, amountPaise, SplitType.EQUAL, parts,
                                 template + " period " + period));      // the id carries the period: replay-safe
        return out;
    }
}

// ---- ext: the audit view -- every version of one expense, and one user's passbook
/**
 * Reads the append-only log the group already keeps. Nothing new is stored: an edit left version 1 marked EDITED
 * beside version 2, and a delete left the row marked DELETED, which is the whole audit trail.
 */
class AuditView {
    /** Every version of one expense, oldest first. */
    static List<Expense> historyOf(Group g, String expenseId) {
        List<Expense> out = new ArrayList<>();
        for (Expense e : g.history()) if (e.id().equals(expenseId)) out.add(e);
        return out;
    }
    /** A user's passbook: every version of every expense they paid for or had a share in, oldest first. */
    static List<Expense> passbook(Group g, String userId) {
        List<Expense> out = new ArrayList<>();
        for (Expense e : g.history())
            if (e.payerId().equals(userId) || e.shares().stream().anyMatch(s -> s.userId().equals(userId))) out.add(e);
        return out;
    }
    /** One line per version: who paid, how much, what happened to it. */
    static String print(Group g, String expenseId) {
        StringBuilder sb = new StringBuilder();
        for (Expense e : historyOf(g, expenseId))
            sb.append("  v").append(e.version()).append(" ").append(e.status()).append(" ")
              .append(e.payerId()).append(" ").append(Money.fmt(e.totalPaise())).append(" ").append(e.note()).append("\n");
        return sb.toString();
    }
}

// ---- ext: one atomic merge per pair -- rung 2 of the ladder, for a group with thousands of members
/**
 * The same arithmetic with no group lock at all: each PAIR is its own key in a concurrent map, and a debt moves
 * with one atomic merge. Two expenses that touch different pairs never wait for each other; two that touch the
 * same pair are ordered by the map, not by a lock you wrote. The key is the two ids in sorted order and the
 * value is signed, so "a owes b" and "b owes a" are still one number and still cannot drift.
 * What it costs: the whole expense is no longer one step, so a reader can see half of a five-way split. Take it
 * only when move 8's arithmetic says the single lock is actually the bottleneck.
 */
class PairLedger {
    private final ConcurrentHashMap<String, Long> pairs = new ConcurrentHashMap<>();
    private static String key(String a, String b) { return a.compareTo(b) < 0 ? a + "|" + b : b + "|" + a; }

    /**
     * Move `paise` of debt from `debtor` to `creditor`, safe from any number of threads with no lock of ours:
     * merge() changes one key atomically, briefly locking only that key's slot in the map (it is not lock-free).
     */
    void move(String debtor, String creditor, long paise) {
        long signed = debtor.compareTo(creditor) < 0 ? paise : -paise;      // sign says which way round the pair is
        pairs.merge(key(debtor, creditor), signed, (x, y) -> x + y == 0 ? null : x + y);   // null removes the key
    }
    /** How much `debtor` owes `creditor` right now, never negative. */
    long owed(String debtor, String creditor) {
        long v = pairs.getOrDefault(key(debtor, creditor), 0L);
        long forward = debtor.compareTo(creditor) < 0 ? v : -v;
        return Math.max(forward, 0);
    }
    /** How many pairs are still live. A settled pair is removed, so a settled group costs nothing. */
    int livePairs() { return pairs.size(); }
}

// ---- ext: persistence -- the two maps behind a repository, and the idempotent write in SQL
/**
 * The seam: the ledger's work as calls a database can answer. The group would be handed one of these instead of
 * building its own Ledger, and its order (split, check, apply, publish) stays the same. Shown for the nets; the
 * who-owes-whom map is the same shape with a (debtor, creditor) key.
 */
interface LedgerRepository {
    /** Add delta to one person's net, atomically. */
    void addToNet(String groupId, String userId, long deltaPaise);
    /** Record that this expense id has been applied; false means it already had been. */
    boolean claim(String groupId, String expenseId);
    /** One person's net in one group. */
    long netOf(String groupId, String userId);
}
/** The in-memory implementation, which is what the group uses today wearing a different coat. */
class InMemoryLedgerRepository implements LedgerRepository {
    private final Map<String, Long> net = new ConcurrentHashMap<>();
    private final Set<String> applied = ConcurrentHashMap.newKeySet();
    public void addToNet(String groupId, String userId, long delta) { net.merge(groupId + "/" + userId, delta, Long::sum); }
    public boolean claim(String groupId, String expenseId) { return applied.add(groupId + "/" + expenseId); }
    public long netOf(String groupId, String userId) { return net.getOrDefault(groupId + "/" + userId, 0L); }
}
// the tables are the maps and the log:
//   grp(id)   member(group_id, user_id)   balance(group_id, user_id, paise)   pair(group_id, debtor, creditor, paise)
//   expense(id, version, group_id, kind, payer, amount_paise, status)   share(expense_id, version, user_id, paise)
// the same write in SQL: ONE transaction per expense, in the group's order.
//   SELECT id FROM grp WHERE id = ? FOR UPDATE;
//     -- the group's lock, now a row lock held until COMMIT: two servers take turns per group, so the
//     -- membership check and "may carol leave?" still see a group nobody else is changing
//   INSERT INTO expense (id, version, group_id, payer, amount_paise) VALUES (?,1,?,?,?) ON CONFLICT DO NOTHING;
//     -- 0 rows inserted means a retry: ROLLBACK, the ledger was already moved
//   INSERT INTO balance (group_id, user_id, paise) VALUES (?,?,?)
//     ON CONFLICT (group_id, user_id) DO UPDATE SET paise = balance.paise + EXCLUDED.paise;   -- once per person
//     -- an atomic add that also creates the row the first time; a bare UPDATE would skip a brand-new member
//   COMMIT;

// ---- ext: the simplification is a suggestion -- prove the plan is valid, and say why greedy is a heuristic
/** Checks a plan the way a reviewer would: does paying it clear everyone, and is it not more than n-1 payments. */
class SimplifyProof {
    /** True when applying every transfer leaves every single person at zero. */
    static boolean settlesEveryone(Map<String, Long> net, List<Transfer> plan) {
        Map<String, Long> after = new TreeMap<>(net);
        for (Transfer t : plan) { after.merge(t.from(), t.paise(), Long::sum); after.merge(t.to(), -t.paise(), Long::sum); }
        return after.values().stream().allMatch(v -> v == 0);
    }
    /** Greedy never needs more than n-1 payments, because each one zeroes at least one person. */
    static boolean withinBound(Map<String, Long> net, List<Transfer> plan) {
        long people = net.values().stream().filter(v -> v != 0).count();
        return plan.size() <= Math.max(people - 1, 0);
    }
    // and the honest caveat: greedy is not always the MINIMUM. a owes 400 and b owes 300; c, d and e are owed
    // 200, 200 and 300. Greedy pays a->e 300, b->c 200, a->d 100, b->d 100: four payments. Three would do
    // (a->c 200, a->d 200, b->e 300), because {a, c, d} and {b, e} each sum to zero and settle on their own.
    // Finding such groups is a search over subsets (NP-hard in general), so the product ships the greedy plan
    // and calls it "simplified", not "minimal".
}

// ---- ext: auto-simplify -- what a group shows as "who owes whom" with the toggle on; the log is untouched
/**
 * The Splitwise toggle, as a view. It changes nothing: it builds a fresh ledger from the suggested transfers,
 * with the same net for every person but far fewer live pairs, and a group with the toggle on shows that one
 * instead of its pairwise map. The expense log and the real ledger are untouched, so switching it off loses nothing.
 */
class AutoSimplify {
    /** A new ledger holding only the simplified transfers. Same nets, fewer pairs. */
    static Ledger collapse(Map<String, Long> net, SimplifyStrategy strategy) {
        Ledger collapsed = new Ledger();
        for (Transfer t : strategy.simplify(net))                         // "to paid t.paise on behalf of from"
            collapsed.apply(t.to(), List.of(new Share(t.from(), t.paise())), +1);
        return collapsed;
    }
}

// ---- ext: the true minimum -- when the interviewer says greedy is not the fewest payments (LeetCode 465)
/**
 * The fewest payments, exactly. People whose balances sum to zero can settle among themselves in one payment fewer
 * than their number, so: fewest payments = people with a balance - the most zero-sum groups they split into.
 * best[m] is that most-groups count for the set of people m (a bitmask: one bit per person), built from smaller sets;
 * a walk back cuts out the groups, and greedy settles inside each. O(n * 2^n) for n people with a balance: instant
 * at 15, too slow past about 20, which is why greedy stays the default.
 */
class FewestPayments implements SimplifyStrategy {
    public List<Transfer> simplify(Map<String, Long> net) {
        List<String> ids = new ArrayList<>();
        for (Map.Entry<String, Long> e : new TreeMap<>(net).entrySet()) if (e.getValue() != 0) ids.add(e.getKey());
        int n = ids.size();
        if (n > 20) return new MinCashFlow().simplify(net);                   // 2^20 sets is the practical ceiling
        long[] sum = new long[1 << n];
        int[] best = new int[1 << n];
        for (int m = 1; m < 1 << n; m++) {
            sum[m] = sum[m & (m - 1)] + net.get(ids.get(Integer.numberOfTrailingZeros(m)));   // m minus its lowest bit
            for (int i = 0; i < n; i++) if ((m >> i & 1) == 1) best[m] = Math.max(best[m], best[m ^ (1 << i)]);
            if (sum[m] == 0) best[m]++;                                         // m closes one more zero-sum group
        }
        List<Transfer> plan = new ArrayList<>();
        int m = (1 << n) - 1, top = m;                                          // walk back from everyone
        while (m != 0) {
            int want = best[m] - (sum[m] == 0 ? 1 : 0), i = 0;
            while ((m >> i & 1) == 0 || best[m ^ (1 << i)] != want) i++;        // drop a person without losing a group
            m ^= 1 << i;
            if (sum[m] == 0) { plan.addAll(settle(ids, net, top ^ m)); top = m; }   // top minus m is one zero-sum group
        }
        return plan;
    }
    /** Greedy inside one zero-sum group: k people, at most k - 1 payments. */
    private static List<Transfer> settle(List<String> ids, Map<String, Long> net, int group) {
        Map<String, Long> part = new TreeMap<>();
        for (int i = 0; i < ids.size(); i++) if ((group >> i & 1) == 1) part.put(ids.get(i), net.get(ids.get(i)));
        return new MinCashFlow().simplify(part);
    }
}

// ---- ext: many groups -- join a group, and one user's balance across every group they are in
/**
 * A user is in many groups. The directory keeps user -> group ids, updated on every create, join and leave that goes
 * through it, so "Bob, everywhere" reads only Bob's groups. Each group is read under its own lock: every number is
 * exact, but the total is not one frozen instant across groups, which is fine for a screen.
 */
class Directory {
    private final Splitwise app;
    private final Map<String, Set<String>> groupsOf = new ConcurrentHashMap<>();   // user -> ids of their groups
    /** Every create, join and leave goes through here, so the index never misses one. */
    Directory(Splitwise app) { this.app = app; }
    /** Create a group through the app, and index every member. */
    Group create(String groupId, String... members) {
        Group g = app.newGroup(groupId, members);
        for (String u : members) index(u).add(groupId);
        return g;
    }
    /** Join: the group adds the member under its own lock, then the index learns it. */
    void join(String groupId, String userId) { app.group(groupId).addMember(userId); index(userId).add(groupId); }
    /** Leave: the group refuses while the net there is not zero; the index forgets only after the group agreed. */
    void leave(String groupId, String userId) { app.group(groupId).removeMember(userId); index(userId).remove(groupId); }
    /** What the whole app owes this user: their net summed over every group they are in. */
    long netEverywhere(String userId) {
        long total = 0;
        for (String gid : index(userId)) total += app.group(gid).netOf(userId);
        return total;
    }
    /** How much `debtor` owes `creditor` over every group they share, after netting; never negative. */
    long owesEverywhere(String debtor, String creditor) {
        long signed = 0;
        for (String gid : index(debtor)) {
            Group g = app.group(gid);
            signed += g.owes(debtor, creditor) - g.owes(creditor, debtor);
        }
        return Math.max(signed, 0);
    }
    /** This user's group ids, a thread-safe set made on first use. */
    private Set<String> index(String userId) { return groupsOf.computeIfAbsent(userId, k -> ConcurrentHashMap.newKeySet()); }
}

/** Runs every extension above so none of them can rot. */
class ExtDemo {
    public static void main(String[] args) {
        Splitwise app = new Splitwise();

        // a fourth split rule: one new class, one registry line
        Group flat = app.newGroup("flat", "ann", "ben", "cal");
        // SplitType is an enum, so a brand-new SHARES constant would be the one extra edit. To show the drop-in
        // without it, the weights rule is registered on the PERCENT key: the group, the ledger, the checks and
        // the tests are all untouched, which is exactly the point.
        flat.configure(new LinkedHashMap<>(Map.of(SplitType.EQUAL, new EqualSplit(), SplitType.EXACT, new ExactSplit(),
                                                  SplitType.PERCENT, new SharesSplit())), new MinCashFlow());
        flat.addExpense("w1", "ann", Money.rupees("400.00"), SplitType.PERCENT,
            List.of(new Participant("ann", 2), new Participant("ben", 1), new Participant("cal", 1)), "rent 2:1:1");
        System.out.println("shares 2:1:1 of 400.00 -> " + flat.history().get(0).shares());

        // fairness: the odd paise move around
        RotatingRemainderSplit rot = new RotatingRemainderSplit();
        List<Participant> three = List.of(Participant.of("ann"), Participant.of("ben"), Participant.of("cal"));
        for (int i = 0; i < 3; i++) System.out.println("rotating 100 paise across 3 -> " + rot.split(100, "ann", three));

        // multi-currency: a euro debt and a rupee debt never mix
        MultiCurrencyLedger mc = new MultiCurrencyLedger();
        mc.apply("INR", "ann", List.of(new Share("ben", 30000)), +1);
        mc.apply("EUR", "ben", List.of(new Share("ann", 2000)), +1);
        FxRates fx = (minor, from, to) -> from.equals(to) ? minor : from.equals("EUR") ? minor * 90 : minor / 90;
        System.out.println("ann: INR net " + Money.fmt(mc.netOf("INR", "ann")) + ", EUR net " + Money.fmt(mc.netOf("EUR", "ann"))
            + ", shown in INR " + Money.fmt(mc.netIn("INR", "ann", fx)));

        // two friends, no group
        Group pair = Friends.between(app, "ben", "ann");
        pair.addExpense("f1", "ann", Money.rupees("120.00"), SplitType.EQUAL,
            List.of(Participant.of("ann"), Participant.of("ben")), "coffee");
        System.out.println("friends " + pair.id() + ": ben owes ann " + Money.fmt(pair.owes("ben", "ann"))
            + "; the same pair the other way round is " + Friends.between(app, "ann", "ben").id());

        // recurring rent, posted twice on purpose
        Group house = app.newGroup("house", "ann", "ben");
        long start = 1_700_000_000_000L, month = 30L * 24 * 3600 * 1000;
        Recurring rent = new Recurring("rent", "ann", Money.rupees("20000.00"),
            List.of(Participant.of("ann"), Participant.of("ben")), start, month);
        rent.post(house, start + 2 * month);
        rent.post(house, start + 2 * month);                                        // the job ran twice
        System.out.println("recurring rent: " + house.history().size() + " expenses (3 periods, posted once each)");

        // edit, delete, and the audit view
        house.edit("rent#0", "ann", Money.rupees("21000.00"), SplitType.EQUAL,
            List.of(Participant.of("ann"), Participant.of("ben")), "rent period 0 (raised)");
        System.out.print("audit of rent#0:\n" + AuditView.print(house, "rent#0"));

        // ladder rung 2: the same pair moved from many threads with no lock of our own
        PairLedger pl = new PairLedger();
        pl.move("ann", "ben", 5000);
        pl.move("ben", "ann", 5000);                                                // the pair nets to zero
        System.out.println("pair ledger: ben owes ann " + Money.fmt(pl.owed("ben", "ann"))
            + ", live pairs " + pl.livePairs());

        // persistence seam
        LedgerRepository repo = new InMemoryLedgerRepository();
        if (repo.claim("house", "x1")) { repo.addToNet("house", "ann", 5000); repo.addToNet("house", "ben", -5000); }
        if (repo.claim("house", "x1")) { repo.addToNet("house", "ann", 5000); repo.addToNet("house", "ben", -5000); }
        System.out.println("repository after the same write twice: ann " + Money.fmt(repo.netOf("house", "ann")));

        // simplify: the plan is valid, and collapsing keeps every net
        Group trip = app.newGroup("trip", "a", "b", "c", "d");
        trip.addExpense("t1", "a", Money.rupees("400.00"), SplitType.EQUAL,
            List.of(Participant.of("a"), Participant.of("b"), Participant.of("c"), Participant.of("d")), "villa");
        trip.addExpense("t2", "b", Money.rupees("120.00"), SplitType.EQUAL,
            List.of(Participant.of("c"), Participant.of("d")), "tickets");
        Map<String, Long> net = trip.balances();
        List<Transfer> plan = trip.simplify();
        System.out.println("plan " + plan + " settles everyone=" + SimplifyProof.settlesEveryone(net, plan)
            + " within n-1=" + SimplifyProof.withinBound(net, plan));
        Ledger collapsed = AutoSimplify.collapse(net, new MinCashFlow());
        System.out.println("auto-simplified ledger has the same nets: " + collapsed.netSnapshot().equals(net));

        // the true minimum: greedy makes four payments here, where three would do
        Map<String, Long> tricky = Map.of("a", -40000L, "b", -30000L, "c", 20000L, "d", 20000L, "e", 30000L);
        System.out.println("greedy " + new MinCashFlow().simplify(tricky).size() + " payments; fewest "
            + new FewestPayments().simplify(tricky));

        // many groups: one user's balance everywhere, a join, and a passbook
        Directory dir = new Directory(new Splitwise());
        Group goa = dir.create("goa", "ann", "ben");
        Group home = dir.create("home", "ann", "ben", "cal");
        goa.addExpense("g1", "ann", Money.rupees("300.00"), SplitType.EQUAL,
            List.of(Participant.of("ann"), Participant.of("ben")), "taxi");
        home.addExpense("h1", "ben", Money.rupees("90.00"), SplitType.EQUAL,
            List.of(Participant.of("ann"), Participant.of("ben"), Participant.of("cal")), "milk");
        dir.join("goa", "cal");
        System.out.println("ben everywhere " + Money.fmt(dir.netEverywhere("ben")) + "; ben owes ann everywhere "
            + Money.fmt(dir.owesEverywhere("ben", "ann")) + "; cal's passbook at home " + AuditView.passbook(home, "cal"));
    }
}
