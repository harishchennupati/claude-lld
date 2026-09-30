import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_deadlock {
static class Bank {
    void transfer(Account from, Account to, long amt) {
        Account first = from.id < to.id ? from : to, second = first == from ? to : from;   // canonical order
        synchronized (first) { synchronized (second) { from.balance -= amt; to.balance += amt; } }
    }
    static class Account { final int id; long balance; Account(int id) { this.id = id; } }
}
static class Striped {
    private final java.util.concurrent.locks.ReentrantLock[] stripes = new java.util.concurrent.locks.ReentrantLock[16];
    Striped() { for (int i = 0; i < 16; i++) stripes[i] = new java.util.concurrent.locks.ReentrantLock(); }
    java.util.concurrent.locks.ReentrantLock forKey(Object k) { return stripes[(k.hashCode() & 0x7fffffff) % 16]; }
}
}
