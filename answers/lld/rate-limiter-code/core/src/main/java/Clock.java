// Time, handed in. Production: System::currentTimeMillis. A demo moves its own clock by hand,
// so "200 ms later" takes no time at all.
interface Clock {
    long nowMillis();
}
