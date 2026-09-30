import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/**
 * Targeted failure tests: each one proves a claim the design makes on page 02, move 9. Every wait in this file has a
 * deadline and the whole run has a watchdog, because a threading test that hangs has told you nothing: a bug has to
 * show up as a FAIL line, never as a build that never ends.
 */
public class FailureTests {
    static int failures = 0;

    /** Prints one line per claim and remembers whether it held. */
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }

    /** A turn-taking test suite that hangs is a failed test suite: this daemon ends the run if one does. */
    static void watchdog(long seconds) {
        Thread t = new Thread(() -> {
            try { Thread.sleep(seconds * 1000); } catch (InterruptedException e) { return; }
            System.out.println("FAIL watchdog: the tests did not finish in " + seconds + " s (a lost wakeup or a stall)");
            Runtime.getRuntime().halt(2);
        });
        t.setDaemon(true);
        t.start();
    }

    /** "1 2 3 ... n " -- what the round robin must produce, whatever the number of threads. */
    static String counted(int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 1; i <= n; i++) b.append(i).append(' ');
        return b.toString();
    }

    public static void main(String[] args) throws Exception {
        watchdog(45);
        MonitorPrinter p = new MonitorPrinter();

        // 1. two threads, one flag: strict alternation, and the output is exactly the expected string.
        String fooBar = p.run(5, Roles.fooBar());
        check(fooBar.equals("foobarfoobarfoobarfoobarfoobar"),
              "FooBar(5) is exactly foobar x5 -- two threads, strict alternation (" + fooBar + ")");

        // 2. three threads on the same flag: zero fires before every number, parity picks the printer.
        String zeo = p.run(5, Roles.zeroEvenOdd());
        check(zeo.equals("0102030405"), "ZeroEvenOdd(5) is exactly 0102030405 -- three threads, one flag (" + zeo + ")");

        // 3. four threads and no flag at all: the four guards partition every i, so the number IS the state machine.
        String fizz = p.run(15, Roles.fizzBuzz());
        check(fizz.equals("12fizz4buzzfizz78fizzbuzz11fizz1314fizzbuzz"),
              "FizzBuzz(15) is exactly right with four guards and no turn flag (" + fizz + ")");

        // 4. the race, 300 times over: the threads really do contend, and the answer is byte-identical every run,
        //    with every token present exactly once -- nothing lost, nothing printed twice.
        String want = "foobar".repeat(120);
        boolean stable = true;
        RoleTally tally = new RoleTally();
        MonitorPrinter repeat = new MonitorPrinter();
        repeat.addObserver(tally);
        for (int r = 0; r < 300; r++) if (!repeat.run(120, Roles.fooBar()).equals(want)) stable = false;
        check(stable, "300 separate runs of FooBar(120) are byte-identical: the order is not luck");
        check(tally.of("foo") == 300 * 120 && tally.of("bar") == 300 * 120,
              "each thread emitted exactly its own 36,000 tokens -- no duplicate, no omission");

        // 5. a stray wake-up cannot move a thread: a storm of signalAll lands during the run and the while loop
        //    absorbs every one of them. wakeups() proves the storm really arrived.
        MonitorPrinter stormed = new MonitorPrinter();
        Thread storm = new Thread(() -> { while (!Thread.currentThread().isInterrupted()) stormed.nudge(); });
        storm.setDaemon(true);
        storm.start();
        String underStorm = p.run(400, Roles.fizzBuzz());
        String stormOut = stormed.run(400, Roles.fizzBuzz());
        storm.interrupt();
        storm.join(2_000);
        check(stormOut.equals(underStorm) && stormed.wakeups() > 400,
              "under a storm of stray wake-ups the sequence is still exact (" + stormed.wakeups() + " wakes for 400 tokens)");

        // 6. ten threads, strict turns: the same engine with a guard set of any size.
        String ten = p.run(600, Roles.roundRobin(10));
        check(ten.equals(counted(600)), "ten threads printed 1..600 in strict order");

        // 7. the three builds are interchangeable: same series, same string, every time.
        boolean same = true;
        for (SeriesPrinter b : List.of(new MonitorPrinter(), new ConditionPrinter(), new SemaphorePrinter())) {
            same &= b.run(5, Roles.fooBar()).equals("foobarfoobarfoobarfoobarfoobar");
            same &= b.run(5, Roles.zeroEvenOdd()).equals("0102030405");
            same &= b.run(15, Roles.fizzBuzz()).equals("12fizz4buzzfizz78fizzbuzz11fizz1314fizzbuzz");
        }
        check(same, "the monitor, the per-role condition and the semaphore builds return the same string for all three series");

        // 8. the herd, counted: signalAll wakes threads that cannot act, an aimed signal does not.
        MonitorPrinter herd = new MonitorPrinter();
        ConditionPrinter aimed = new ConditionPrinter();
        SemaphorePrinter baton = new SemaphorePrinter();
        herd.run(4_000, Roles.fizzBuzz());
        aimed.run(4_000, Roles.fizzBuzz());
        baton.run(4_000, Roles.fizzBuzz());
        check(herd.wastedWakeups() > 0 && aimed.wastedWakeups() == 0 && baton.wastedWakeups() == 0,
              "the herd is real: signalAll wasted " + herd.wastedWakeups() + " wakes over 4000 tokens, an aimed signal wasted 0");

        // 9. a slow listener cannot break the order, because it is called with the lock released.
        MonitorPrinter slow = new MonitorPrinter();
        slow.addObserver((role, token, at) -> { try { Thread.sleep(1); } catch (InterruptedException e) { Thread.currentThread().interrupt(); } });
        check(slow.run(60, Roles.fooBar()).equals("foobar".repeat(60)),
              "a listener that sleeps a millisecond per step slows only itself: the sequence is still exact");

        // 10. a listener that throws on every step cannot break the run either.
        MonitorPrinter broken = new MonitorPrinter();
        broken.addObserver((role, token, at) -> { throw new RuntimeException("the dashboard is down"); });
        check(broken.run(15, Roles.fizzBuzz()).equals("12fizz4buzzfizz78fizzbuzz11fizz1314fizzbuzz"),
              "a listener that throws on every step is swallowed: the sequence is still exact");

        // 11. a stall must fail, not hang: a guard set with a hole (fizzbuzz removed) reaches i = 15 with no role
        //     able to act, and the deadline turns that into an exception in under a second.
        MonitorPrinter holed = new MonitorPrinter();
        holed.configure(Sink.NONE, System::currentTimeMillis, 600);
        long t0 = System.currentTimeMillis();
        boolean threw = false;
        try { holed.run(15, Roles.fizzBuzz().subList(0, 3)); } catch (IllegalStateException e) { threw = true; }
        long tookMs = System.currentTimeMillis() - t0;
        check(threw && tookMs < 4_000, "a guard set with a hole fails in " + tookMs + " ms instead of hanging for ever");

        // 12. a role whose action throws must not strand the others: the run ends with an exception inside the
        //     deadline, and exactly the turns that succeeded were published.
        AtomicInteger published = new AtomicInteger();
        AtomicInteger acts = new AtomicInteger();
        MonitorPrinter fragile = new MonitorPrinter();
        fragile.configure(Sink.NONE, System::currentTimeMillis, 800);
        fragile.addObserver((role, token, at) -> published.incrementAndGet());
        List<Role> fragileRoles = List.of(
            new Rule("foo", s -> s.phase == 0, s -> { s.phase = 1; return "foo"; }),
            new Rule("bar", s -> s.phase == 1, s -> {
                if (acts.incrementAndGet() == 5) throw new IllegalArgumentException("this role is broken");
                s.phase = 0; s.i++; return "bar";
            }));
        boolean threwRole = false;
        try { fragile.run(20, fragileRoles); } catch (IllegalStateException e) { threwRole = true; }
        check(threwRole && published.get() == 9,
              "a role that throws on its fifth turn ends the run cleanly: 9 turns committed, nobody left asleep for ever");

        // 13. stop() ends a long run: the threads leave, and what was printed before the signal is intact.
        MonitorPrinter live = new MonitorPrinter();
        AtomicReference<String> streamed = new AtomicReference<>("");
        AtomicBoolean failed = new AtomicBoolean();
        Thread runner = new Thread(() -> {
            try { streamed.set(live.run(Integer.MAX_VALUE, Roles.roundRobin(4))); }
            catch (Exception e) { failed.set(true); }
        });
        runner.start();
        Thread.sleep(40);
        live.stop();
        runner.join(5_000);
        String prefix = streamed.get();
        check(!failed.get() && !runner.isAlive() && prefix.length() > 0 && counted(2_000_000).startsWith(prefix),
              "stop() ended an unbounded run: " + prefix.length() + " characters out, every thread finished, the prefix is exact");

        // 14. the edges: nothing to print, and one thing to print.
        boolean edges = p.run(0, Roles.fooBar()).isEmpty()
                     && p.run(0, Roles.fizzBuzz()).isEmpty()
                     && p.run(1, Roles.fooBar()).equals("foobar")
                     && p.run(1, Roles.zeroEvenOdd()).equals("01")
                     && p.run(1, Roles.fizzBuzz()).equals("1");
        check(edges, "n = 0 prints nothing and every thread still exits; n = 1 is correct for all three series");

        // 15. the deadline comes from the injected clock, so a test proves it without waiting for it.
        MonitorPrinter fake = new MonitorPrinter();
        fake.configure(Sink.NONE, new Clock() {
            private long t = System.currentTimeMillis();
            public long nowMs() { long now = t; t += 1_000_000; return now; }   // every reading is a thousand seconds later
        }, 5_000);
        long t1 = System.currentTimeMillis();
        boolean gaveUp = false;
        try { fake.run(200_000, Roles.fizzBuzz()); } catch (IllegalStateException e) { gaveUp = true; }
        long fakeMs = System.currentTimeMillis() - t1;
        check(gaveUp && fakeMs < 3_000,
              "a clock already past the deadline makes the printer give up in " + fakeMs + " ms of real time");

        // 16. an interrupt while a thread is parked on await(): the finally releases the lock on the way out, so the
        //     run fails at its deadline instead of hanging AND the very same printer is still usable afterwards.
        MonitorPrinter cancelled = new MonitorPrinter();
        cancelled.configure(Sink.NONE, System::currentTimeMillis, 700);
        AtomicReference<String> ended = new AtomicReference<>("did not end");
        Thread host = new Thread(() -> {
            try { cancelled.run(Integer.MAX_VALUE, Roles.roundRobin(3)); }
            catch (IllegalStateException e) { ended.set("threw"); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
        });
        host.start();
        Thread.sleep(40);
        boolean hit = Interrupts.interruptRole("t1");
        host.join(5_000);
        String after = cancelled.run(15, Roles.fizzBuzz());
        check(hit && "threw".equals(ended.get()) && !host.isAlive()
              && after.equals("12fizz4buzzfizz78fizzbuzz11fizz1314fizzbuzz"),
              "a thread interrupted while waiting kills the run cleanly and leaves the lock free: the same printer runs again");

        // 17. the Phaser build needs TWO barrier trips per token -- one for the reads, one for the write -- and with
        //     them it agrees with the lock builds character for character.
        check(new PhaserPrinter().run(15, Roles.fizzBuzz()).equals("12fizz4buzzfizz78fizzbuzz11fizz1314fizzbuzz"),
              "the Phaser build, with the reads and the write in separate phases, gives the same string as the lock");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures > 0) System.exit(1);
    }
}
