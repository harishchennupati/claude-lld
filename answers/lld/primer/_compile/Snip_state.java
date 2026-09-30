import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_state {
interface VmState { VmState insertCoin(Vm vm); VmState select(Vm vm); }
static class Idle implements VmState {
    public VmState insertCoin(Vm vm) { vm.credit++; return new HasCoin(); }
    public VmState select(Vm vm) { throw new IllegalStateException("insert a coin first"); }
}
static class HasCoin implements VmState {
    public VmState insertCoin(Vm vm) { vm.credit++; return this; }
    public VmState select(Vm vm) { vm.credit--; vm.dispensed++; return vm.credit > 0 ? this : new Idle(); }
}
static class Vm {
    int credit, dispensed; private VmState state = new Idle();
    void insertCoin() { state = state.insertCoin(this); }
    void select() { state = state.select(this); }
}
enum OrderStatus { CREATED, PAID, SHIPPED, DELIVERED, CANCELLED }       // simple lifecycles: enum + a transition check
}
