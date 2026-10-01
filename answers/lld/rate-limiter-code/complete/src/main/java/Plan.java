// A plan belongs to the customer and carries its limits.
enum Plan {
    FREE(Limit.perSecond(5), Limit.perDay(10_000)),
    PRO(Limit.perSecond(50), Limit.perDay(1_000_000));

    final Limit rate;
    final Limit daily;

    Plan(Limit rate, Limit daily) {
        this.rate = rate;
        this.daily = daily;
    }
}
