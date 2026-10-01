// "limit: { requests: 2, per: second }": the same limit for every caller.
record FixedLimit(Limit limit) implements LimitPolicy {
    @Override
    public Limit limitFor(Request request) {
        return limit;
    }
}
