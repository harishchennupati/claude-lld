// Time, handed in. Production: System::currentTimeMillis. A demo or a test moves its own clock,
// so "200 ms later" takes no time at all.
interface Clock {
    long nowMillis();
}
