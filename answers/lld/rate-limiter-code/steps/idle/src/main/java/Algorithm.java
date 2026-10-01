// How a rule counts: the "algorithm:" line of the config. A plain enum; CounterFactory turns it
// into a counter.
enum Algorithm {
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG, SLIDING_WINDOW_COUNTER, CREDITS
}
