import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_lsp {
// BEFORE: subtype weakens the contract
static class Bird { void fly() {} }
static class Penguin extends Bird { @Override void fly() { throw new UnsupportedOperationException(); } }   // callers of Bird now crash
// AFTER: model the capability, not the taxonomy
interface Flyer { void fly(); }
static class Sparrow implements Flyer { public void fly() {} }
static class Emperor { void swim() {} }                       // a penguin is simply not a Flyer
void migrate(java.util.List<Flyer> flock) { for (Flyer f : flock) f.fly(); }   // never checks types
}
