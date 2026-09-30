//@ file from x
// LeetCode 362: hit(t) records a hit at second t; getHits(t) counts the hits in the last 300 s.
// Memory must not grow with traffic, so there are 300 slots, one per second of the window. A slot
// remembers which second it is counting; a newer second landing on it starts it again from zero.
class HitCounter {
    private final int[] seconds = new int[300];
    private final int[] counts = new int[300];

    synchronized void hit(int timestamp) {
        int i = timestamp % 300;
        if (seconds[i] != timestamp) {        // this slot still holds a second from 300 s ago or more
            seconds[i] = timestamp;
            counts[i] = 0;
        }
        counts[i]++;
    }

    synchronized int getHits(int timestamp) {
        int total = 0;
        for (int i = 0; i < 300; i++) {
            if (timestamp - seconds[i] < 300) {   // only slots from the last 300 seconds count
                total += counts[i];
            }
        }
        return total;
    }
}
