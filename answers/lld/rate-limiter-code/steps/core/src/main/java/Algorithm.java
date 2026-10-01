// How a rule counts: the "algorithm:" line of the config.
// Why an enum: a closed set of names, checked by the compiler. CounterFactory turns each one into
// a counter.
enum Algorithm {
    TOKEN_BUCKET, FIXED_WINDOW, SLIDING_WINDOW_LOG
}
