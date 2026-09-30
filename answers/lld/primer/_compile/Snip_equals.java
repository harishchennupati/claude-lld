import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_equals {
static final class SpotId {
    private final String floor; private final int number;
    SpotId(String floor, int number) { this.floor = floor; this.number = number; }
    @Override public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof SpotId s)) return false;         // pattern-match instanceof
        return number == s.number && floor.equals(s.floor);
    }
    @Override public int hashCode() { return java.util.Objects.hash(floor, number); }
}
}
