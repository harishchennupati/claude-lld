// One bucket's answer to "may this request spend `cost` tokens now?"
//   allowed           yes or no
//   remaining         whole tokens left after this request
//   retryAfterMillis  if refused, how long until enough tokens are there
record Decision(boolean allowed, long remaining, long retryAfterMillis) {
    static Decision allow(long remaining) {
        return new Decision(true, remaining, 0);
    }

    static Decision deny(long remaining, long retryAfterMillis) {
        return new Decision(false, remaining, retryAfterMillis);
    }
}
