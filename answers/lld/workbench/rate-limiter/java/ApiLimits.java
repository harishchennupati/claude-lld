//@ file from door
// Every limit the API enforces. Each is an ordinary RateLimiter that counts by a different key;
// they are checked in order and the first refusal is the answer.
class ApiLimits {
    private final RateLimiter perSecond;   // per customer, by tier
    private final RateLimiter perDay;      // per customer: the daily quota
    private final RateLimiter search;      // per customer, /search only
    private final RateLimiter anonymous;   // per IP: no customer yet (signing in)
    private final RateLimiter global;      // everyone together

    ApiLimits(RateLimiter perSecond, RateLimiter perDay, RateLimiter search, RateLimiter anonymous,
              RateLimiter global) {
        this.perSecond = perSecond;
        this.perDay = perDay;
        this.search = search;
        this.anonymous = anonymous;
        this.global = global;
    }

    Decision check(Request request) {
        Decision d;
        if (request.customerId() == null) {
            d = anonymous.check(request.ip());              // the IP is all we know
        } else {
            String customer = request.customerId();
            d = perSecond.check(customer);
            if (d.allowed()) {
                d = perDay.check(customer);
            }
            if (d.allowed() && "/search".equals(request.endpoint())) {
                d = search.check(customer);
            }
        }
        if (d.allowed()) {
            d = global.check("everyone");                  // last: its one counter is the busiest
        }
        return d;
    }
}
