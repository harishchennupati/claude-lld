import java.util.*;
import java.util.concurrent.*;

// Reference code for every follow-up on page 05. Each block is a new class behind an existing seam: a rule
// (DispatchStrategy, DoorPolicy), a listener (ElevatorObserver) or a caller. The one exception is fire recall,
// whose mode lives in the bank (recallAll / endRecall), because only the bank can switch off the car buttons.

// ---- ext: the 9am rule change. Idle cars wait in the lobby and up-calls from the lobby win.
/**
 * Morning rush: bias the score so an idle car near the lobby wins an up-call, and a car already carrying a
 * crowd loses. Wraps the normal rule instead of replacing it, so the physics of the estimate stay shared.
 */
class UpPeakDispatch implements DispatchStrategy {
    private final int bottom, top;
    UpPeakDispatch(int bottom, int top) { this.bottom = bottom; this.top = top; }

    public ElevatorCar pick(List<ElevatorCar> cars, HallCall call) {
        ElevatorCar best = null; int bestScore = Integer.MAX_VALUE;
        for (ElevatorCar c : cars) {
            CarSnapshot s = c.snapshot();
            int score = NearestCarStrategy.cost(s, call, bottom, top);     // reuse the normal estimate
            if (call.floor() == bottom && s.heading() == Direction.IDLE) score -= 5;   // park the idle ones at the lobby
            if (s.pendingStops() > 4) score += 3;                                      // spread the crowd
            if (score < bestScore) { best = c; bestScore = score; }
        }
        return best;
    }
}

// ---- ext: where idle cars wait. At nine in the morning they should wait in the lobby, not where they stopped.
/**
 * Parking. Any car standing still away from the lobby is sent back to it, so the next up-call is answered
 * from floor 0 instead of floor 14. It is a caller, not a rule: it presses the ordinary car button, so the
 * bank and the car do not change. Run it on a timer, or after each tick.
 */
class LobbyParking {
    private final ElevatorSystem bank;
    private final int lobbyFloor;
    LobbyParking(ElevatorSystem bank, int lobbyFloor) { this.bank = bank; this.lobbyFloor = lobbyFloor; }

    /** Sends every idle car that is not already at the lobby back to it; returns how many were sent. */
    int park() {
        int sent = 0;
        for (CarSnapshot s : bank.snapshots())                 // snapshots need no lock; each press takes it once
            if (s.state() == CarState.IDLE && s.floor() != lobbyFloor) {
                try { bank.requestCar(s.carId(), lobbyFloor); sent++; }
                catch (IllegalStateException e) { /* a zoned car that cannot reach the lobby, or a fire recall */ }
            }
        return sent;
    }
}

// ---- ext: energy at night. Starting a parked car costs more power than letting a moving one carry on.
/**
 * Energy-saving scoring: the normal estimate plus a penalty for any car standing still, whose motor would have
 * to start. A car already on its way wins the call even when a parked car is a floor or two closer.
 */
class EnergySavingDispatch implements DispatchStrategy {
    private final int bottom, top, wakePenalty;
    EnergySavingDispatch(int bottom, int top, int wakePenalty) { this.bottom = bottom; this.top = top; this.wakePenalty = wakePenalty; }

    public ElevatorCar pick(List<ElevatorCar> cars, HallCall call) {
        ElevatorCar best = null; int bestScore = Integer.MAX_VALUE;
        for (ElevatorCar c : cars) {
            CarSnapshot s = c.snapshot();
            int score = NearestCarStrategy.cost(s, call, bottom, top);
            if (s.heading() == Direction.IDLE) score += wakePenalty;                 // a parked car's motor must start
            if (score < bestScore) { best = c; bestScore = score; }
        }
        return best;
    }
}

// ---- ext: express and zoned cars. A decorator: filter the candidates, then defer to any scorer.
/**
 * Zoning: cars are allowed only inside their zone, so a candidate outside it is dropped before scoring. The
 * scoring rule underneath is untouched, and the LOOK sweep never hears about zones at all.
 */
class ZonedDispatch implements DispatchStrategy {
    private final DispatchStrategy base;
    private final Map<Integer, int[]> zones;                       // carId -> {lowest floor, highest floor}
    ZonedDispatch(DispatchStrategy base, Map<Integer, int[]> zones) { this.base = base; this.zones = zones; }

    public ElevatorCar pick(List<ElevatorCar> cars, HallCall call) {
        List<ElevatorCar> allowed = new ArrayList<>();
        for (ElevatorCar c : cars) {
            int[] z = zones.get(c.id);
            if (z == null || (call.floor() >= z[0] && call.floor() <= z[1])) allowed.add(c);
        }
        return allowed.isEmpty() ? null : base.pick(allowed, call);   // null = nobody may take it; it waits
    }
}

// ---- ext: capacity and weight. Load is tracked beside the car so the base stays capacity-free.
/** Riders and kilos on board one car, and the two limits that stop it answering another hall call. */
class CarLoad {
    final int maxRiders, maxKg;
    private int riders, kg;
    CarLoad(int maxRiders, int maxKg) { this.maxRiders = maxRiders; this.maxKg = maxKg; }
    /** Someone stepped in. Returns false, changing nothing, if the car is already at a limit. */
    synchronized boolean board(int weightKg) {
        if (riders + 1 > maxRiders || kg + weightKg > maxKg) return false;
        riders++; kg += weightKg; return true;
    }
    synchronized void leave(int weightKg) { riders = Math.max(0, riders - 1); kg = Math.max(0, kg - weightKg); }
    synchronized boolean full() { return riders >= maxRiders || kg >= maxKg; }
}

/** Skip cars that are full, then defer to the rule underneath. A full car keeps sweeping; it just stops answering. */
class CapacityAwareDispatch implements DispatchStrategy {
    private final DispatchStrategy base;
    private final Map<Integer, CarLoad> load;
    CapacityAwareDispatch(DispatchStrategy base, Map<Integer, CarLoad> load) { this.base = base; this.load = load; }

    public ElevatorCar pick(List<ElevatorCar> cars, HallCall call) {
        List<ElevatorCar> roomy = new ArrayList<>();
        for (ElevatorCar c : cars) { CarLoad l = load.get(c.id); if (l == null || !l.full()) roomy.add(c); }
        return roomy.isEmpty() ? null : base.pick(roomy, call);
    }
}

// ---- ext: the door rule changes too. The lobby needs longer doors than floor seventeen.
/** Longer dwell at the lobby, the normal dwell everywhere else. One class, one configure() line. */
class LobbyDwellPolicy implements DoorPolicy {
    private final int lobbyFloor, lobbyTicks, normalTicks;
    LobbyDwellPolicy(int lobbyFloor, int lobbyTicks, int normalTicks) {
        this.lobbyFloor = lobbyFloor; this.lobbyTicks = lobbyTicks; this.normalTicks = normalTicks;
    }
    public int dwellTicks(int carId, int floor) { return floor == lobbyFloor ? lobbyTicks : normalTicks; }
}

// ---- ext: maintenance mode -- take no new calls, finish the ones owed, then go out of service
/**
 * Maintenance that can wait for the trip to end. A draining car is left out of every dispatch, keeps serving
 * the stops it already owes, and is taken out of service as soon as its snapshot shows it standing idle with
 * nothing owed. A filter plus a listener: the bank and the car do not change.
 */
class DrainForService implements DispatchStrategy, ElevatorObserver {
    private final DispatchStrategy base;
    private final ElevatorSystem bank;
    private final Set<Integer> draining = ConcurrentHashMap.newKeySet();
    DrainForService(DispatchStrategy base, ElevatorSystem bank) { this.base = base; this.bank = bank; }

    /** Ask for maintenance on this car: from now on it takes no new hall call. */
    void drain(int carId) { draining.add(carId); }

    /** Leave out the draining cars, then defer to the rule underneath. Null when nobody is left: the call waits. */
    public ElevatorCar pick(List<ElevatorCar> cars, HallCall call) {
        List<ElevatorCar> others = new ArrayList<>();
        for (ElevatorCar c : cars) if (!draining.contains(c.id)) others.add(c);
        return others.isEmpty() ? null : base.pick(others, call);
    }
    /** Its last stop is served and its doors are shut: now take it out, with nothing owed and nobody waiting. */
    public void onChange(CarSnapshot s) {
        if (s.state() == CarState.IDLE && s.pendingStops() == 0 && draining.remove(s.carId()))
            bank.takeOutOfService(s.carId());
    }
}

// ---- ext: destination dispatch -- riders type where they are going in the lobby
/** One rider's whole trip, typed on the keypad before boarding. */
record Trip(int from, int to) {
    /** The way this rider travels, which is also the leg their pickup goes on. */
    Direction dir() { return to > from ? Direction.UP : Direction.DOWN; }
}

/**
 * Destination dispatch. The keypad knows each rider's floor before they board, so a rider is sent to a car
 * that is already collecting riders for that floor, and told which car to stand at. The pickup is an ordinary
 * hall call; the destination is pressed only when that car opens at the pickup going the rider's way, so the
 * car can never serve it before the rider is on board. A rule for the choice and a listener for the boarding.
 */
class DestinationDispatch implements DispatchStrategy, ElevatorObserver {
    private final ElevatorSystem bank;
    private final DispatchStrategy base;
    private final Map<HallCall, Integer> typed = new ConcurrentHashMap<>();        // pickup being placed -> its destination
    private final Map<Integer, List<Trip>> waiting = new ConcurrentHashMap<>();    // carId -> riders told to board it
    DestinationDispatch(ElevatorSystem bank, DispatchStrategy base) { this.bank = bank; this.base = base; }

    /** The keypad: "I am on 0, I want 12". Returns the car to stand at, or -1 when no car can take it yet. */
    int enter(int from, int to) {
        Trip trip = new Trip(from, to);
        typed.put(new HallCall(from, trip.dir()), to);
        int carId = bank.requestHall(from, trip.dir());
        if (carId >= 0) waiting.computeIfAbsent(carId, k -> new CopyOnWriteArrayList<>()).add(trip);
        return carId;
    }

    /** A car already collecting riders for this floor, going this way; failing that, the normal rule. */
    public ElevatorCar pick(List<ElevatorCar> cars, HallCall call) {
        Integer to = typed.get(call);
        if (to != null)
            for (ElevatorCar c : cars)
                for (Trip t : waiting.getOrDefault(c.id, List.of()))
                    if (t.to() == to && t.dir() == call.direction()) return c;     // same floor, same way: same car
        return base.pick(cars, call);
    }

    /** Boarding: the car opened at a waiting rider's floor, going their way. Now, and only now, press their floor. */
    public void onChange(CarSnapshot s) {
        if (s.doors() != DoorState.OPEN) return;
        List<Trip> list = waiting.getOrDefault(s.carId(), List.of());
        for (Trip t : list)
            if (t.from() == s.floor() && (s.heading() == t.dir() || s.heading() == Direction.IDLE) && list.remove(t))
                bank.requestCar(s.carId(), t.to());            // remove() first, so a second listener call presses nothing
    }
}

// ---- ext: request feasibility -- nobody may sit through more than five stops (Microsoft's version)
/**
 * One car's plan for the sweep it is on, one per direction: the floors it will stop at and the trips it has
 * taken. A new trip is taken only if, with its two floors added, nobody (the newcomer included) sits through
 * more than maxStops stops and no more than maxRiders are ever on board. Stops already made stay in the plan
 * until the sweep ends, so a rider who has sat through three is not promised five more.
 */
class StopBudget {
    private final int maxStops, maxRiders;
    private final TreeSet<Integer> stops = new TreeSet<>();      // every floor this sweep stops at: made or planned
    private final List<Trip> trips = new ArrayList<>();          // every trip taken on this sweep
    StopBudget(int maxStops, int maxRiders) { this.maxStops = maxStops; this.maxRiders = maxRiders; }

    /** Check and record in one synchronized step. False changes nothing: the rider waits for the next sweep. */
    synchronized boolean tryTake(Trip next) {
        TreeSet<Integer> after = new TreeSet<>(stops); after.add(next.from()); after.add(next.to());
        List<Trip> all = new ArrayList<>(trips); all.add(next);
        for (Trip r : all) if (stopsRidden(after, r) > maxStops) return false;
        for (int f : after) if (onBoardLeaving(all, f) > maxRiders) return false;
        stops.addAll(after); trips.add(next);
        return true;
    }
    /** The car has turned round: this sweep is over and everyone on it has got out. */
    synchronized void sweepEnded() { stops.clear(); trips.clear(); }

    /** Stops a rider sits through: every stop after the one they board at, up to and including their own. */
    static int stopsRidden(TreeSet<Integer> stops, Trip r) {
        return r.dir() == Direction.UP ? stops.subSet(r.from(), false, r.to(), true).size()
                                       : stops.subSet(r.to(), true, r.from(), false).size();
    }
    /** Riders inside as the car leaves floor f: boarded there or earlier, getting out further on. */
    private static int onBoardLeaving(List<Trip> trips, int f) {
        int n = 0;
        for (Trip r : trips)
            if (r.dir() == Direction.UP ? r.from() <= f && f < r.to() : r.to() < f && f <= r.from()) n++;
        return n;
    }
}

// ---- ext: fire service -- every car to the recall floor; no call is answered and the buttons inside are off
/**
 * The fire panel's side of recall. The bank owns the mode, because only the bank can hold every hall call AND
 * switch off the buttons inside the cars in one locked step; this class engages it, watches for every car to
 * arrive, and releases it. The waiting calls survive the whole thing and are offered again after the release.
 */
class FireService {
    private final ElevatorSystem bank;
    private final int recallFloor;
    FireService(ElevatorSystem bank, int recallFloor) { this.bank = bank; this.recallFloor = recallFloor; }

    /** Engage: every car drops its stops and heads for the recall floor; hall presses wait, car buttons do nothing. */
    void engage() { bank.recallAll(recallFloor); }
    /** True once every car still in service stands at the recall floor. */
    boolean complete() {
        for (CarSnapshot s : bank.snapshots())
            if (s.state() != CarState.MAINTENANCE && s.floor() != recallFloor) return false;
        return true;
    }
    /** Release: the buttons work again and the queued calls are picked up on the next tick. */
    void release() { bank.endRecall(); }
}

// ---- ext: the cheap query -- "how long until a car reaches 7?" answered off snapshots, no lock
/**
 * The lobby board. It asks the bank's estimate, which scores the published snapshots of the cars that could
 * take that call with the dispatcher's own cost, and turns floors into milliseconds. O(cars), no lock, no scan.
 */
class EtaBoard {
    private final ElevatorSystem bank;
    private final long msPerFloor;
    EtaBoard(ElevatorSystem bank, long msPerFloor) { this.bank = bank; this.msPerFloor = msPerFloor; }

    /** Milliseconds of travel until a car could open its doors there, or -1 when no car can come. */
    long etaMs(int floor, Direction direction) {
        int floors = bank.estimateFloorsToServe(new HallCall(floor, direction));   // snapshots and final fields only
        return floors < 0 ? -1 : floors * msPerFloor;
    }
}

// ---- ext: persistence -- the assignment index becomes a repository, and the claim becomes a conditional UPDATE
/**
 * Who owes which call, behind an interface so it can live in a database when one controller serves forty
 * buildings. claim() is the whole invariant: exactly one car may win a call.
 */
interface AssignmentRepository {
    /** Claim the call for this car. False means another controller already claimed it; nothing was written. */
    boolean claim(HallCall call, int carId);
    /** Give the call up: it was served, or the car died. */
    void release(HallCall call);
    /** Which car owes it, if any. */
    Optional<Integer> owner(HallCall call);
}

/** The in-memory one. putIfAbsent is a compare-and-set (write only if nobody has, in one step): the lock's idea again. */
class InMemoryAssignmentRepository implements AssignmentRepository {
    private final Map<HallCall, Integer> rows = new ConcurrentHashMap<>();
    public boolean claim(HallCall call, int carId) { return rows.putIfAbsent(call, carId) == null; }
    public void release(HallCall call)             { rows.remove(call); }
    public Optional<Integer> owner(HallCall call)  { return Optional.ofNullable(rows.get(call)); }
}
// the same claim in SQL, once two controllers run on two machines:
// UPDATE hall_call SET car_id = ? WHERE building = ? AND floor = ? AND direction = ? AND car_id IS NULL;
//   -- 1 row updated = this controller won it;  0 rows = the other one did, and it must pick again

/** Runs every extension once so the file is proven, not just written. */
class ExtDemo {
    public static void main(String[] args) {
        int bottom = 0, top = 19;
        List<ElevatorCar> cars = List.of(new ElevatorCar(0, bottom, top, 0),
                                         new ElevatorCar(1, bottom, top, 9),
                                         new ElevatorCar(2, bottom, top, 18));
        ElevatorSystem bank = new ElevatorSystem(cars, bottom, top);
        DispatchStrategy nearest = new NearestCarStrategy(bottom, top);

        // 1. the 9am rule change: a new class and one configure line
        bank.configure(new UpPeakDispatch(bottom, top), new LobbyDwellPolicy(0, 3, 1));
        System.out.println("up-peak: a lobby up-call went to car " + bank.requestHall(0, Direction.UP));

        // 2. parking: the idle cars go back to the lobby to wait for the rush
        System.out.println("parking: idle cars sent back to the lobby = " + new LobbyParking(bank, bottom).park());

        // 2b. energy at night: a car already climbing past takes the call instead of waking a parked one
        ElevatorSystem night = new ElevatorSystem(List.of(new ElevatorCar(0, bottom, top, 8), new ElevatorCar(1, bottom, top, 11)), bottom, top);
        night.requestCar(0, 15); night.tick();                  // car 0 is now climbing through 9; car 1 stands at 11
        night.configure(new EnergySavingDispatch(bottom, top, 5), new FixedDwellPolicy(1));
        System.out.println("energy: 12 UP went to car " + night.requestHall(12, Direction.UP)
                         + " (the nearest-car rule would wake car 1, one floor away)");

        // 3. zoning: cars 0-1 serve the low rise, car 2 the high rise
        Map<Integer, int[]> zones = Map.of(0, new int[]{0, 9}, 1, new int[]{0, 9}, 2, new int[]{10, 19});
        bank.configure(new ZonedDispatch(nearest, zones), new FixedDwellPolicy(1));
        System.out.println("zoned: floor 15 went to car " + bank.requestHall(15, Direction.DOWN)
                         + ", floor 4 went to car " + bank.requestHall(4, Direction.UP));

        // 4. capacity: a full car is skipped, and the one with room answers
        Map<Integer, CarLoad> load = new HashMap<>();
        for (ElevatorCar c : cars) load.put(c.id, new CarLoad(8, 680));
        while (load.get(1).board(70)) { }                         // car 1 is now full
        bank.configure(new CapacityAwareDispatch(nearest, load), new FixedDwellPolicy(1));
        System.out.println("capacity: car 1 is full, so floor 9 went to car " + bank.requestHall(9, Direction.UP));

        // 5. destination dispatch: two riders bound for 17 are grouped into one car, and both get there. A
        //    fresh bank, so the grouping is what decides and not a hall call this demo already assigned above.
        ElevatorSystem lobby = new ElevatorSystem(List.of(new ElevatorCar(0, bottom, top, 0),
                                                          new ElevatorCar(1, bottom, top, 1)), bottom, top);
        DestinationDispatch dd = new DestinationDispatch(lobby, new NearestCarStrategy(bottom, top));
        lobby.configure(dd, new FixedDwellPolicy(1));
        lobby.addObserver(dd);                                     // it listens for the doors, to press 17 at boarding
        int first = dd.enter(0, 17), second = dd.enter(1, 17);
        for (int t = 0; t < 30; t++) lobby.tick();
        System.out.println("destination dispatch: riders from floors 0 and 1, both going to 17, board car "
                         + first + " / " + second + " (must be the same car); it is now at floor "
                         + lobby.car(first).floor() + " owing " + lobby.car(first).pendingStops() + " stops");

        // 6. request feasibility: Microsoft's example, at most five stops for anyone on board
        StopBudget up = new StopBudget(5, 20);
        boolean a = up.tryTake(new Trip(0, 10)), b = up.tryTake(new Trip(1, 7)), c = up.tryTake(new Trip(8, 9));
        System.out.println("five-stop rule: 0->10, 1->7, 8->9 taken " + a + "/" + b + "/" + c
                         + "; 4->6 taken " + up.tryTake(new Trip(4, 6)) + " (0->10 would sit through 7 stops)"
                         + "; 7->9 taken " + up.tryTake(new Trip(7, 9)) + " (no new floor)");

        // 7. maintenance mode: car 2 takes no new calls, finishes what it owes, then goes out of service
        DrainForService maintenance = new DrainForService(nearest, bank);
        bank.configure(maintenance, new FixedDwellPolicy(1));
        bank.addObserver(maintenance);
        maintenance.drain(2);
        for (int t = 0; t < 60 && bank.car(2).state() != CarState.MAINTENANCE; t++) bank.tick();
        System.out.println("maintenance mode: car 2 finished its stops and is now " + bank.car(2).state()
                         + " at floor " + bank.car(2).floor());

        // 8. the cheap query, off snapshots and with no lock
        EtaBoard board = new EtaBoard(bank, 2000);
        System.out.println("eta to floor 7 going up: " + board.etaMs(7, Direction.UP) + " ms");

        // 9. fire service: every car home, calls held, buttons inside off; then release
        FireService fire = new FireService(bank, 0);
        bank.requestHall(12, Direction.DOWN);
        fire.engage();
        System.out.println("fire recall engaged; calls waiting = " + bank.pendingCalls().size());
        try { bank.requestCar(0, 7); System.out.println("a car button worked during recall!"); }
        catch (IllegalStateException e) { System.out.println("during recall: " + e.getMessage()); }
        for (int t = 0; t < 60 && !fire.complete(); t++) bank.tick();
        System.out.println("every car in service is at the recall floor: " + fire.complete());
        fire.release();
        bank.tick();
        System.out.println("after the release the waiting calls are being served again: "
                         + (bank.pendingCalls().size() < bank.outstandingCalls()));

        // 10. persistence: the same claim, but a row instead of a map entry
        AssignmentRepository repo = new InMemoryAssignmentRepository();
        HallCall call = new HallCall(7, Direction.UP);
        System.out.println("repository claim: first=" + repo.claim(call, 1) + " second=" + repo.claim(call, 2)
                         + " owner=" + repo.owner(call).orElse(-1));
    }
}
