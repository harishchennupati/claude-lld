// The ways of counting. A plain enum: the store switches on it to make a new counter.
enum Algorithm {
    //@ until windows
    TOKEN_BUCKET
    //@ end
    //@ from windows until credits
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG, SLIDING_WINDOW_COUNTER
    //@ end
    //@ from credits
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG, SLIDING_WINDOW_COUNTER, CREDITS
    //@ end
}
