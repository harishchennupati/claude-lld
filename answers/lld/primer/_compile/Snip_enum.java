import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_enum {
enum SpotType {
    SMALL(10), COMPACT(20), LARGE(40);          // each constant carries its hourly rate
    final int rate;
    SpotType(int rate) { this.rate = rate; }
}
enum Op {                                       // constants with behaviour
    ADD { int apply(int a, int b) { return a + b; } },
    MUL { int apply(int a, int b) { return a * b; } };
    abstract int apply(int a, int b);
}
int price(SpotType t, int hours) { return t.rate * hours; }
java.util.EnumMap<SpotType, Integer> free = new java.util.EnumMap<>(SpotType.class);
}
