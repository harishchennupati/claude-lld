// A customer's plan, and the limit it carries.
enum Tier {
    FREE(Limit.perSecond(5)),
    PRO(Limit.perSecond(50));

    final Limit limit;

    Tier(Limit limit) {
        this.limit = limit;
    }
}
