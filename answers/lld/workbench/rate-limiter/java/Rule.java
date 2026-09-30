//@ file from f4
import java.util.function.Function;
import java.util.function.Predicate;

// One limit, applied to one kind of key.
//   name       shown when this rule refuses a request, and on a dashboard
//   appliesTo  which requests it covers: every request, or only those to /search
//   key        whose budget a request spends: "fantasy-app", "fantasy-app /search", or "*" for everyone
//   limiter    this rule's buckets, one per key
record Rule(String name, Predicate<Request> appliesTo, Function<Request, String> key, ClientRateLimiter limiter) {
}
