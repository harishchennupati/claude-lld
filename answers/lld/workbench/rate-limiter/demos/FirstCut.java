import java.util.HashMap;
import java.util.Map;

// The 15-minute version everybody writes first: one class does everything. It works for one
// rule on one server. The design on this page is what each interviewer push turns it into.
class FirstCutLimiter {
    private final Map<String, double[]> buckets = new HashMap<>();   // client -> {tokens, last}

    synchronized boolean allow(String clientId) {
        long now = System.currentTimeMillis();
        double[] b = buckets.get(clientId);
        if (b == null) {
            b = new double[] {5, now};
            buckets.put(clientId, b);
        }
        b[0] = Math.min(5, b[0] + (now - b[1]) / 200.0);            // refill: 200 ms a token
        b[1] = now;
        if (b[0] < 1) {
            return false;
        }
        b[0] -= 1;
        return true;
    }
}

public class FirstCut {
    public static void main(String[] args) {
        FirstCutLimiter limiter = new FirstCutLimiter();
        StringBuilder answers = new StringBuilder();
        for (int i = 0; i < 7; i++) {
            answers.append(limiter.allow("score-widget") ? " yes" : " no");
        }
        System.out.println("7 requests at once:" + answers);
    }
}
