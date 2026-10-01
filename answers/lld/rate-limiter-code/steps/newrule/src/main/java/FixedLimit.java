// "limit: { fixed: 2 per second }": the same limit for every caller.
// Why a record: it is one value. A record can implement an interface like any class.
record FixedLimit(Limit limit) implements LimitPolicy {
    @Override
    public Limit limitFor(Request request) {
        return limit;
    }
}
