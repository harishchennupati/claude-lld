// Time, passed in through the constructor rather than read inside. Production passes
// System::currentTimeMillis; a demo passes a clock it moves by hand, so "200 ms later" takes no
// time at all.
interface Clock {
    long nowMillis();
}
