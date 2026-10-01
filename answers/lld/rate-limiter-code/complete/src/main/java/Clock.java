// Time, handed in rather than read inside.
// Why an interface with one method: production passes System::currentTimeMillis, which fits any
// one-method interface; a demo passes a clock it moves by hand, so "200 ms later" takes no time.
interface Clock {
    long nowMillis();
}
