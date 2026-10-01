// How a rule counts: the "algorithm:" line of the config. A plain enum; CounterFactory turns it
// into a counter.
enum Algorithm {
    //@ until windows
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG
    //@ end
    //@ from windows until credits
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG, SLIDING_WINDOW_COUNTER
    //@ end
    //@ from credits
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG, SLIDING_WINDOW_COUNTER, CREDITS
    //@ end
}
