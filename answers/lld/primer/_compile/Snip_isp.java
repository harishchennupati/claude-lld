import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.*;

class Snip_isp {
// BEFORE: one fat interface
interface Machine { void print(); void scan(); void fax(); }
static class BasicPrinter implements Machine { public void print() {} public void scan() { throw new UnsupportedOperationException(); } public void fax() { throw new UnsupportedOperationException(); } }
// AFTER: roles
interface Printer { void print(); }
interface Scanner { void scan(); }
static class Simple implements Printer { public void print() {} }
static class AllInOne implements Printer, Scanner { public void print() {} public void scan() {} }
}
