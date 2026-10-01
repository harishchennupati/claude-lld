// A plan belongs to the customer and carries its limits. A new plan (ENTERPRISE) is one new
// line here, not an edit to every rule.
// Why an enum with fields: a closed set of plans, where each value also carries data, set through
// the enum's constructor. (When plans come from the config file, this becomes a record loaded at
// startup; nothing else changes.)
enum Plan {
    FREE(Limit.perSecond(5), Limit.perDay(10_000)),
    PRO(Limit.perSecond(50), Limit.perDay(1_000_000));

    final Limit rate;      // the per-second speed limit
    final Limit daily;     // the allowance for the calendar day

    Plan(Limit rate, Limit daily) {
        this.rate = rate;
        this.daily = daily;
    }
}
