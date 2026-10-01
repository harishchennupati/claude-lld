// "limit: 2 per second": the same for everyone.
record FixedLimit(Limit limit) implements LimitPolicy {
    @Override
    public Limit limitFor(Request request) {
        return limit;
    }
}
