// LeetCode 362: hit(t) records a hit at second t; getHits(t) counts the hits in the last
// 300 s. Memory must not grow with traffic, so there are 300 slots, one per second of the
// window. A slot remembers which second it counts; a newer second landing on it starts again.
class HitCounter {
    private final int[] seconds = new int[300];
    private final int[] counts = new int[300];

    synchronized void hit(int timestamp) {
        int i = timestamp % 300;
        if (seconds[i] != timestamp) {    // the slot holds a second from 300 s ago or more
            seconds[i] = timestamp;
            counts[i] = 0;
        }
        counts[i]++;
    }

    synchronized int getHits(int timestamp) {
        int total = 0;
        for (int i = 0; i < 300; i++) {
            if (timestamp - seconds[i] < 300) {   // only the last 300 seconds count
                total += counts[i];
            }
        }
        return total;
    }
}
