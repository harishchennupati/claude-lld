import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_composition {
// inheritance explosion: SportsCarWithSunroofAndTurbo ...
// composition: one class, capabilities plugged in
interface Engine { int hp(); }
interface Roof { boolean opens(); }
static class Turbo implements Engine { public int hp() { return 300; } }
static class Sunroof implements Roof { public boolean opens() { return true; } }
static final class Car {
    private final Engine engine; private final Roof roof;
    Car(Engine e, Roof r) { engine = e; roof = r; }
    int hp() { return engine.hp(); }
}
}
