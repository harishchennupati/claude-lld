// A token bucket whose two numbers live in Redis. It holds no state itself: each call sends
// SCRIPT, which refills, checks and takes on the Redis server as ONE step, because Redis runs
// one script at a time. The script is the whole fleet's version of `synchronized`.
class RedisTokenBucket implements Bucket {
    // KEYS[1]: the bucket, e.g. "rl:plan|fantasy-app|50/1000ms". ARGV: capacity, ms per token,
    // cost. A text block (Java 15+) keeps the script readable here.
    static final String SCRIPT = """
            local capacity, perToken, cost = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
            local t = redis.call('TIME')           -- Redis's clock: the servers' clocks disagree
            local now = t[1] * 1000 + math.floor(t[2] / 1000)
            local b = redis.call('HMGET', KEYS[1], 'tokens', 'last')
            local tokens, last = tonumber(b[1]) or capacity, tonumber(b[2]) or now
            if now > last then
              tokens = math.min(capacity, tokens + (now - last) / perToken)
              last = now
            end
            local allowed, wait = 0, 0
            if tokens >= cost then
              tokens = tokens - cost; allowed = 1
            else
              wait = math.ceil((cost - tokens) * perToken)
            end
            redis.call('HSET', KEYS[1], 'tokens', tokens, 'last', last)
            -- an idle bucket deletes itself once it would be full again anyway
            redis.call('PEXPIRE', KEYS[1], math.ceil(capacity * perToken))
            return {allowed, math.floor(tokens), wait}
            """;

    private final FakeRedis redis;   // in production: EVALSHA of SCRIPT (EVAL again on NOSCRIPT:
    private final String key;        // a restarted Redis has an empty script cache)
    private final Limit limit;
    private final boolean failOpen;

    RedisTokenBucket(FakeRedis redis, String key, Limit limit, boolean failOpen) {
        this.redis = redis;
        this.key = key;
        this.limit = limit;
        this.failOpen = failOpen;
    }

    @Override
    public Decision tryConsume(int cost, long nowMillis) {       // Redis uses its own clock
        if (cost > limit.capacity()) {
            return Decision.never(0);
        }
        try {
            long[] r = redis.tokenBucket(key, limit.capacity(), limit.millisPerToken(), cost);
            return r[0] == 1 ? Decision.allow(r[1]) : Decision.deny(r[1], r[2]);
        } catch (IllegalStateException unreachable) {
            // Fail open: the limiter going down must not take the API down with it. We do not
            // know what is left, so say the whole budget: polite clients must not slow down.
            // Fail closed where a flood is worse than an outage, such as sign-ins.
            return failOpen ? Decision.allow(limit.capacity()) : Decision.deny(0, 1_000);
        }
    }

    @Override
    public void refund(int cost, long nowMillis) {
        try {
            redis.refund(key, limit.capacity(), cost);
        } catch (IllegalStateException unreachable) {
            // Nothing to give back to: the tokens were never taken if Redis was down.
        }
    }
}
