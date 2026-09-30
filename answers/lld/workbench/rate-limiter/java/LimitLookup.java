//@ file from f4
// "Which limit applies to this key?" The limiter needs only this one question answered, so it
// depends on this one-method interface instead of on Plans. Plans answers it for clients, and a
// rule with the same limit for every key is a lambda: key -> Limit.perSecond(2).
@FunctionalInterface
interface LimitLookup {
    Limit limitFor(String key);
}
