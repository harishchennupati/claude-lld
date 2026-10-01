// How a rule counts. A plain enum: the store switches on it to make a new counter.
enum Algorithm {
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG, SLIDING_WINDOW_COUNTER, CREDITS
}
