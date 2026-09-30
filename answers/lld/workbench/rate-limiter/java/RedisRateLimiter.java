//@ file from f8
// The budget lives in Redis, so every server spends from the same one. One Lua script does
// refill + check + take on the Redis server as ONE step: Redis runs one script at a time, so the
// script is the whole fleet's version of `synchronized`. The API still sees a RateLimiter:
// this class replaces ClientRateLimiter, and nothing that calls tryAcquire changes.
class RedisRateLimiter implements RateLimiter {
    static final String SCRIPT = """
            -- KEYS[1] = this client's bucket, e.g. "rl:fantasy-app"; ARGV = capacity, ms per token, cost
            local capacity, perToken, cost = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
            local t = redis.call('TIME')              -- Redis's clock: the servers' own clocks disagree
            local now = t[1] * 1000 + math.floor(t[2] / 1000)
            local b = redis.call('HMGET', KEYS[1], 'tokens', 'last')
            local tokens, last = tonumber(b[1]) or capacity, tonumber(b[2]) or now
            if now > last then
              tokens = math.min(capacity, tokens + (now - last) / perToken)
              last = now
            end
            local allowed = 0
            if tokens >= cost then tokens = tokens - cost; allowed = 1 end
            redis.call('HSET', KEYS[1], 'tokens', tokens, 'last', last)
            redis.call('PEXPIRE', KEYS[1], math.ceil(capacity * perToken))   -- an idle bucket deletes itself
            return {allowed, math.floor(tokens), math.ceil(math.max(0, cost - tokens) * perToken)}
            """;

    private final LimitLookup limits;
    private final FakeRedis redis;      // in production: a Redis client that runs SCRIPT with EVALSHA
    private final boolean failOpen;     // if Redis is unreachable: allow (most endpoints) or refuse (logins)?

    RedisRateLimiter(LimitLookup limits, FakeRedis redis, boolean failOpen) {
        this.limits = limits;
        this.redis = redis;
        this.failOpen = failOpen;
    }

    @Override
    public Decision tryAcquire(String clientId, int cost) {
        Limit limit = limits.limitFor(clientId);
        if (cost > limit.capacity()) {
            return Decision.never(0);
        }
        try {
            long[] r = redis.tokenBucket("rl:" + clientId, limit.capacity(), limit.millisPerToken(), cost);
            return r[0] == 1 ? Decision.allow(r[1]) : Decision.deny(r[1], r[2]);
        } catch (IllegalStateException unreachable) {
            // Fail open: an outage of the limiter should not become an outage of the API.
            // Fail closed where a flood is worse than an outage, such as logins.
            return failOpen ? Decision.allow(0) : Decision.deny(0, 1_000);
        }
    }
}
