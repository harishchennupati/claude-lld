import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_ocp {
// BEFORE: every new method edits this switch
double feeBefore(String type, double amt) {
    switch (type) { case "CARD": return amt * 0.02; case "UPI": return 0; default: throw new IllegalArgumentException(); }
}
// AFTER: a new method is a new class registered once
interface FeePolicy { double fee(double amt); }
static class CardFee implements FeePolicy { public double fee(double a) { return a * 0.02; } }
static class UpiFee implements FeePolicy { public double fee(double a) { return 0; } }
java.util.Map<String, FeePolicy> policies = new java.util.HashMap<>(java.util.Map.of("CARD", new CardFee(), "UPI", new UpiFee()));
double fee(String type, double amt) { return policies.get(type).fee(amt); }
}
