// Time, handed in rather than read inside. Production passes System::currentTimeMillis; a demo or
// a test passes a clock it moves by hand, so "200 ms later" takes no time at all.
interface Clock {
    long nowMillis();
}
