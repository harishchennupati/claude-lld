import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_interface {
interface PricingStrategy {
    double price(long minutes);
    default double priceHours(long h) { return price(h * 60); }   // shared fallback, no state
}
static abstract class Vehicle {                        // shared state + a hook
    final String plate;
    Vehicle(String plate) { this.plate = plate; }
    abstract int wheels();
}
static class Car extends Vehicle { Car(String p) { super(p); } int wheels() { return 4; } }
}
