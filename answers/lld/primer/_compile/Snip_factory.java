import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_factory {
interface Vehicle { int wheels(); }
static class Bike implements Vehicle { public int wheels() { return 2; } }
static class Car implements Vehicle { public int wheels() { return 4; } }
static class VehicleFactory {
    private static final java.util.Map<String, java.util.function.Supplier<Vehicle>> REG =
        new java.util.HashMap<>(java.util.Map.of("bike", Bike::new, "car", Car::new));
    static Vehicle create(String type) {
        var s = REG.get(type.toLowerCase());
        if (s == null) throw new IllegalArgumentException("unknown vehicle: " + type);
        return s.get();
    }
    static void register(String type, java.util.function.Supplier<Vehicle> s) { REG.put(type, s); }   // new type, no edit
}
}
