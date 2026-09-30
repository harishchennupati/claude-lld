import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Thirteen claims the design makes, each with the test that proves it. Every one reproduces a bug a bank of
// lifts really has: a call sent to two cars, a car in maintenance still being fed, a button that does not exist,
// a sweep that turns early or runs on to the top of the shaft, an emergency stop that swallows the queue, a broken
// or out-of-order listener, a button that queues three stops, a wait time read off the wall clock, a car going up
// that puts out the down lamp, doors that close on a rider holding OPEN, the slower car sent, a car button obeyed
// during fire recall, and a keypad rider carried to their floor before they were even on board.
public class FailureTests {
    static int failures = 0;
    static void check(boolean ok, String what) {
        System.out.println((ok ? "PASS " : "FAIL ") + what);
        if (!ok) failures++;
    }
    /** A fresh bank: n cars in a twenty-floor tower, all standing at the lobby unless told otherwise. */
    static ElevatorSystem bank(int cars, int... startFloors) {
        List<ElevatorCar> list = new ArrayList<>();
        for (int i = 0; i < cars; i++) list.add(new ElevatorCar(i, 0, 19, i < startFloors.length ? startFloors[i] : 0));
        ElevatorSystem b = new ElevatorSystem(list, 0, 19);
        b.configure(new NearestCarStrategy(0, 19), new FixedDwellPolicy(1));
        return b;
    }
    /** Stops owed by the whole bank. One per outstanding call is the invariant we keep checking. */
    static int totalStops(ElevatorSystem b) {
        int n = 0;
        for (CarSnapshot s : b.snapshots()) n += s.pendingStops();
        return n;
    }

    public static void main(String[] args) throws Exception {
        // 1. forty riders press the same button at the same instant: one car, one stop, one index entry
        ElevatorSystem b1 = bank(3, 0, 9, 18);
        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Integer>> presses = new ArrayList<>();
        for (int i = 0; i < 40; i++) presses.add(pool.submit(() -> { go.await(); return b1.requestHall(7, Direction.UP); }));
        go.countDown();
        Set<Integer> answered = new HashSet<>();
        for (Future<Integer> f : presses) answered.add(f.get());
        check(answered.size() == 1, "forty presses of 7 UP were answered by exactly one car " + answered);
        check(b1.outstandingCalls() == 1, "the bank owes that call once, not forty times");
        check(totalStops(b1) == 1, "exactly one car has floor 7 in its sweep");

        // ... and six different buttons at the same instant: each gets exactly one car, none is lost
        CountDownLatch go2 = new CountDownLatch(1);
        int[] floors = { 2, 4, 11, 13, 15, 17 };
        List<Future<Integer>> six = new ArrayList<>();
        for (int f : floors) six.add(pool.submit(() -> { go2.await(); return b1.requestHall(f, Direction.DOWN); }));
        go2.countDown();
        int sent = 0;
        for (Future<Integer> f : six) if (f.get() >= 0) sent++;
        pool.shutdown();
        check(sent == 6 && b1.outstandingCalls() == 7, "six simultaneous calls each got a car, none dropped");
        check(totalStops(b1) == 7, "seven calls, seven stops across the bank: no call was given to two cars");

        // 2. a car in maintenance is never assigned, and with every car down the call waits instead of vanishing
        ElevatorSystem b2 = bank(2, 5, 15);
        b2.takeOutOfService(0);
        check(b2.requestHall(6, Direction.UP) == 1, "the nearest car is out of service, so car 1 takes the call");
        check(b2.car(0).pendingStops() == 0, "the car in maintenance was given nothing");
        b2.takeOutOfService(1);
        check(b2.requestHall(3, Direction.UP) == -1, "with every car down the call is not dispatched");
        check(b2.pendingCalls().contains(new HallCall(3, Direction.UP)), "it waits in the queue instead of being lost");
        check(!b2.holdDoors(0, 3) && !b2.closeDoors(0), "the door buttons do nothing in a car that is out of service");
        b2.returnToService(1);
        b2.tick();
        check(b2.assignedCar(new HallCall(3, Direction.UP)) == 1, "a returning car drains the queue on the next tick");

        // 3. a button that does not exist is rejected before anything is touched
        ElevatorSystem b3 = bank(2);
        try { b3.requestHall(99, Direction.UP); check(false, "floor 99 must be rejected"); }
        catch (IllegalArgumentException e) { check(true, "floor 99 is rejected: " + e.getMessage()); }
        try { b3.requestHall(-1, Direction.DOWN); check(false, "floor -1 must be rejected"); }
        catch (IllegalArgumentException e) { check(true, "floor -1 is rejected"); }
        try { b3.requestCar(0, 99); check(false, "a car button for 99 must be rejected"); }
        catch (IllegalArgumentException e) { check(true, "the car button for floor 99 is rejected"); }
        try { b3.requestHall(19, Direction.UP); check(false, "UP on the top floor must be rejected"); }
        catch (IllegalArgumentException e) { check(true, "there is no UP button on the top floor"); }
        try { b3.requestHall(0, Direction.DOWN); check(false, "DOWN on the ground floor must be rejected"); }
        catch (IllegalArgumentException e) { check(true, "there is no DOWN button on the ground floor"); }
        check(b3.outstandingCalls() == 0 && totalStops(b3) == 0, "after five rejections no car owes anything");
        try { new ElevatorSystem(List.of(new ElevatorCar(1, 0, 19, 0), new ElevatorCar(0, 0, 19, 0)), 0, 19);
              check(false, "car ids out of order must be refused: car(1) would return the wrong car"); }
        catch (IllegalArgumentException e) { check(true, "a bank whose car ids are not 0, 1, 2 ... is refused"); }

        // 4. the sweep: never turns early, never runs past its last stop (LOOK, not SCAN), never shows a
        //    direction arrow it is not actually travelling, and serves the call behind it within one sweep
        ElevatorSystem b4 = bank(1);
        b4.requestHall(8, Direction.UP);
        b4.tick(); b4.tick();                                   // the car is climbing, now at floor 2
        b4.requestHall(1, Direction.DOWN);                      // a call behind it: it must be served last
        int previous = b4.car(0).floor(), highest = previous, ticksToServeBoth = -1;
        boolean reachedEight = false, turnedEarly = false, servedLobby = false, arrowLied = false;
        for (int t = 0; t < 40; t++) {
            b4.tick();
            int now = b4.car(0).floor();
            highest = Math.max(highest, now);
            if (!reachedEight && now < previous) turnedEarly = true;
            if (now == 8) reachedEight = true;
            if (reachedEight && now == 1) servedLobby = true;
            if (ticksToServeBoth < 0 && b4.outstandingCalls() == 0) ticksToServeBoth = t + 1;
            CarSnapshot s = b4.car(0).snapshot();
            if (s.state() == CarState.MOVING_UP   && (s.heading() != Direction.UP   || s.doors() != DoorState.CLOSED)) arrowLied = true;
            if (s.state() == CarState.MOVING_DOWN && (s.heading() != Direction.DOWN || s.doors() != DoorState.CLOSED)) arrowLied = true;
            previous = now;
        }
        check(!turnedEarly, "the car never descended while floor 8 was still ahead of it");
        check(reachedEight && servedLobby, "it served floor 8 first and only then came back down to floor 1");
        check(highest == 8, "it turned at its last stop and never ran on to floor 19: LOOK, not SCAN");
        check(!arrowLied, "whenever the panel showed an arrow the car was really moving that way, doors shut");
        check(ticksToServeBoth > 0 && ticksToServeBoth <= 2 * 19,
              "the call behind the car was served inside one sweep of the shaft: " + ticksToServeBoth + " ticks, bound 38");
        check(b4.outstandingCalls() == 0, "both hall calls left the index once their doors opened");

        // 5. an emergency stop leaves the queue intact for another car to retry
        ElevatorSystem b5 = bank(2, 16, 2);
        int owner = b5.requestHall(17, Direction.DOWN);
        check(owner == 0, "the near car takes the call at floor 17");
        b5.takeOutOfService(owner);
        HallCall call = new HallCall(17, Direction.DOWN);
        check(b5.pendingCalls().contains(call), "the emergency stop put the call back on the queue");
        check(b5.outstandingCalls() == 1, "the call still exists: it was moved, not dropped");
        check(b5.car(owner).pendingStops() == 0, "the stopped car owes nothing any more");
        b5.tick();
        check(b5.assignedCar(call) == 1, "one tick later the other car owes it");

        // 6. a display panel that throws cannot break dispatch or the tick
        ElevatorSystem b6 = bank(1);
        b6.addObserver(s -> { throw new RuntimeException("panel is down"); });
        int car = b6.requestHall(4, Direction.UP);
        check(car == 0, "dispatch still answered although the panel threw");
        for (int t = 0; t < 4; t++) b6.tick();
        check(b6.car(0).floor() == 4, "the car still climbed to floor 4 although the panel threw on every change");

        // ... and listeners hear after the lock, from many threads, so two snapshots can arrive in the wrong order.
        //     Four threads press buttons while this one ticks; the maintenance count must still equal the floors moved.
        int wrongCounts = 0;
        for (int trial = 0; trial < 20; trial++) {
            ElevatorSystem bo = bank(1);
            MaintenanceMonitor monitor = new MaintenanceMonitor(1_000_000);
            bo.addObserver(monitor);
            AtomicBoolean stop = new AtomicBoolean();
            ExecutorService pressers = Executors.newFixedThreadPool(4);
            for (int p = 0; p < 4; p++) pressers.submit(() -> {
                Random r = new Random();
                while (!stop.get()) bo.requestHall(1 + r.nextInt(18), r.nextBoolean() ? Direction.UP : Direction.DOWN);
                return null;
            });
            int moved = 0, at = 0;
            for (int t = 0; t < 3000; t++) { bo.tick(); int f = bo.car(0).floor(); moved += Math.abs(f - at); at = f; }
            stop.set(true); pressers.shutdown(); pressers.awaitTermination(5, TimeUnit.SECONDS);
            bo.tick(); moved += Math.abs(bo.car(0).floor() - at);             // one last publish, after the pressers stop
            if (monitor.floorsTravelled(0) != moved) wrongCounts++;
        }
        check(wrongCounts == 0, "with presses racing the ticks, the maintenance count equals the floors really moved (20 runs)");

        // 7. pressing the same button three times is one stop and one door opening
        ElevatorSystem b7 = bank(1);
        b7.requestCar(0, 5); b7.requestCar(0, 5); b7.requestCar(0, 5);
        check(b7.car(0).pendingStops() == 1, "three presses of floor 5 are one stop");
        int openings = 0; DoorState was = DoorState.CLOSED;
        for (int t = 0; t < 12; t++) {
            b7.tick();
            DoorState now = b7.car(0).doors();
            if (now == DoorState.OPEN && was == DoorState.CLOSED && b7.car(0).floor() == 5) openings++;
            was = now;
        }
        check(openings == 1, "the doors opened at floor 5 exactly once");

        // 8. waiting time is read from the injected clock, not the wall clock
        ElevatorSystem b8 = bank(1);
        long[] now = { 0L };
        b8.setClock(() -> now[0]);
        b8.requestHall(3, Direction.UP);                        // pressed at t = 0
        for (int t = 0; t < 4; t++) { now[0] += 500; b8.tick(); }   // four half-second ticks: climb, climb, climb, open
        check(b8.averageWaitMs() == 2000.0, "the rider waited 2000 ms by the test's clock, whatever the wall clock says");

        // 9. a car climbing serves the UP crowd on that floor only: the DOWN lamp stays lit for the next leg
        ElevatorSystem b9 = bank(1);                            // one car, standing at the lobby
        b9.requestHall(6, Direction.UP);                        // two people on floor 6, wanting opposite ways
        b9.requestHall(6, Direction.DOWN);
        check(b9.outstandingCalls() == 2, "UP and DOWN on floor 6 are two different calls, not one");
        for (int t = 0; t < 20 && !(b9.car(0).floor() == 6 && b9.car(0).doors() == DoorState.OPEN); t++) b9.tick();
        check(b9.assignedCar(new HallCall(6, Direction.UP)) < 0, "the UP lamp on 6 went out when the doors opened");
        check(b9.assignedCar(new HallCall(6, Direction.DOWN)) >= 0, "the DOWN lamp on 6 is still lit: nobody served it yet");
        check(b9.car(0).pendingStops() == 1, "floor 6 is still on that car's DOWN leg");
        b9.tick(); b9.tick();                                   // shut the doors, turn, open again going down
        check(b9.outstandingCalls() == 0, "one door cycle later the same car serves the DOWN call at floor 6");

        // 10. the door buttons: OPEN holds, CLOSE lets go, and neither can touch a car that is moving
        ElevatorSystem b10 = bank(1);
        CarPanelButtons inside = new CarPanelButtons(b10, 0);
        b10.requestCar(0, 4);
        check(!inside.holdDoor(3), "the OPEN button does nothing while the car is moving with its doors shut");
        for (int t = 0; t < 6 && b10.car(0).doors() != DoorState.OPEN; t++) b10.tick();
        check(b10.car(0).floor() == 4 && b10.car(0).doors() == DoorState.OPEN, "the doors opened at floor 4");
        check(inside.holdDoor(3), "the OPEN button holds the doors there");
        b10.tick(); b10.tick();
        check(b10.car(0).doors() == DoorState.OPEN && b10.car(0).floor() == 4,
              "two ticks later the doors are still open and the car has not moved a floor");
        check(inside.closeDoor(), "the CLOSE button ends the wait");
        b10.tick();
        check(b10.car(0).doors() == DoorState.CLOSED, "the next tick shuts the doors and the sweep goes on");

        // 11. the bank sends the car that will really get there first, and the lobby board shows that car's number
        ElevatorSystem b11 = bank(2, 10, 3);
        b11.requestCar(0, 12); b11.requestCar(1, 0); b11.tick();   // car 0 now climbs through 11, car 1 descends through 2
        check(b11.requestHall(8, Direction.DOWN) == 0,
              "8 DOWN goes to car 0 (up to the top and back: 19 floors), not car 1 (down, up, down again: 32)");
        CarSnapshot goingDown = new CarSnapshot(0, 1, 10, Direction.DOWN, CarState.MOVING_DOWN, DoorState.CLOSED, 1, 0);
        check(NearestCarStrategy.cost(goingDown, new HallCall(12, Direction.UP), 0, 19) == 22,
              "a car going down at 10 meets an UP call at 12 after one turn: 10 floors down, 12 up");
        ElevatorSystem b11z = new ElevatorSystem(List.of(new ElevatorCar(0, 0, 9, 9), new ElevatorCar(1, 10, 19, 19)), 0, 19);
        check(b11z.estimateFloorsToServe(new HallCall(12, Direction.DOWN)) == 7 && b11z.requestHall(12, Direction.DOWN) == 1,
              "the board says 7 floors for 12 DOWN, the high-rise car's number: the low-rise car cannot reach 12");
        ElevatorSystem b11e = bank(2, 8, 11);
        b11e.requestCar(0, 15); b11e.tick();                        // car 0 climbs through 9; car 1 stands parked at 11
        b11e.configure(new EnergySavingDispatch(0, 19, 5), new FixedDwellPolicy(1));
        check(b11e.requestHall(12, Direction.UP) == 0, "energy rule: the climbing car takes 12 UP (3 floors) instead of waking the parked one (1)");

        // 12. two ways out of normal service. Fire recall: every car home, calls held, the buttons inside off ...
        ElevatorSystem b12 = bank(2, 10, 5);
        FireService fire = new FireService(b12, 0);
        b12.requestHall(12, Direction.DOWN);
        fire.engage();
        check(b12.pendingCalls().contains(new HallCall(12, Direction.DOWN)), "recall hands the 12 DOWN call back to the queue");
        boolean refused = false;
        try { b12.requestCar(0, 7); } catch (IllegalStateException e) { refused = true; }
        check(refused, "during recall the buttons inside a car do nothing");
        check(b12.requestHall(15, Direction.DOWN) == -1, "during recall a new hall call waits instead of getting a car");
        boolean openedOnTheWay = false;
        for (int t = 0; t < 40 && !fire.complete(); t++) {
            b12.tick();
            for (CarSnapshot s : b12.snapshots()) if (s.doors() == DoorState.OPEN && s.floor() != 0) openedOnTheWay = true;
        }
        check(fire.complete() && !openedOnTheWay, "every car went straight to the recall floor and opened nowhere else");
        fire.release(); b12.tick();
        check(b12.pendingCalls().isEmpty() && b12.outstandingCalls() == 2, "after the release both held calls get a car");
        // ... and maintenance mode: take no new call, finish the ones owed, then go out of service
        ElevatorSystem b12m = bank(2, 3, 10);
        DrainForService drainRule = new DrainForService(new NearestCarStrategy(0, 19), b12m);
        b12m.configure(drainRule, new FixedDwellPolicy(1));
        b12m.addObserver(drainRule);
        check(b12m.requestHall(5, Direction.UP) == 0, "car 0 takes the call at floor 5");
        drainRule.drain(0);
        check(b12m.requestHall(4, Direction.DOWN) == 1, "car 0 is draining, so 4 DOWN goes to car 1 although car 0 is nearer");
        for (int t = 0; t < 20 && b12m.car(0).state() != CarState.MAINTENANCE; t++) b12m.tick();
        check(b12m.car(0).state() == CarState.MAINTENANCE && b12m.car(0).floor() == 5
              && b12m.assignedCar(new HallCall(5, Direction.UP)) < 0, "car 0 served the call it owed at 5, then went out of service");

        // 13. riders who type their floor. The destination is pressed only once the rider is on board ...
        ElevatorSystem b13 = bank(1, 15);
        DestinationDispatch keypad = new DestinationDispatch(b13, new NearestCarStrategy(0, 19));
        b13.configure(keypad, new FixedDwellPolicy(1));
        b13.addObserver(keypad);
        keypad.enter(10, 17);                                       // the car is at 15: floor 17 is nearer than the rider
        List<Integer> opened = new ArrayList<>(); DoorState before = DoorState.CLOSED;
        for (int t = 0; t < 40; t++) {
            b13.tick();
            CarSnapshot s = b13.car(0).snapshot();
            if (s.doors() == DoorState.OPEN && before == DoorState.CLOSED) opened.add(s.floor());
            before = s.doors();
        }
        check(opened.equals(List.of(10, 17)), "the car opened at 10 to pick the rider up, then at 17 to let them out " + opened);
        // ... and Microsoft's rule: nobody may sit through more than five stops
        StopBudget budget = new StopBudget(5, 20);
        check(budget.tryTake(new Trip(0, 10)) && budget.tryTake(new Trip(1, 7)) && budget.tryTake(new Trip(8, 9)),
              "0->10, 1->7 and 8->9 fit: the rider from 0 sits through 1, 7, 8, 9 and 10, five stops");
        check(!budget.tryTake(new Trip(4, 6)), "4->6 is refused: the rider from 0 would sit through seven stops");
        check(budget.tryTake(new Trip(7, 9)), "7->9 is taken: it adds no new floor, so nobody's count changes");
        StopBudget roomForTwo = new StopBudget(5, 2);
        check(roomForTwo.tryTake(new Trip(0, 10)) && roomForTwo.tryTake(new Trip(1, 7)) && !roomForTwo.tryTake(new Trip(2, 5)),
              "with room for two riders, a third one riding from 2 to 5 is refused");

        System.out.println(failures == 0 ? "ALL PASS" : failures + " FAILED");
        if (failures != 0) System.exit(1);
    }
}
