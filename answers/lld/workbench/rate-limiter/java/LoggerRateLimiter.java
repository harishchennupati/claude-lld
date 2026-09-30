//@ file from x
import java.util.HashMap;
import java.util.Map;

// LeetCode 359: print a message only if the same message was not printed in the last 10 seconds.
// It is a rate limiter in which every message is a client with a limit of 1 per 10 seconds.
class LoggerRateLimiter {
    private final Map<String, Integer> nextAllowed = new HashMap<>();   // message -> first second it may print again

    boolean shouldPrintMessage(int timestamp, String message) {
        Integer next = nextAllowed.get(message);
        if (next != null && timestamp < next) {
            return false;
        }
        nextAllowed.put(message, timestamp + 10);
        return true;
    }
}
