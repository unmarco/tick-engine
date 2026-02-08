"""Village demo — exercises all extension packages + tick-atlas terrain.

20x20 grid, 8 colonists with hunger/fatigue needs, strength/speed stats.
Uses: tick-spatial (Grid2D, pathfind), tick-schedule (Timer), tick-fsm (FSM),
tick-signal (SignalBus), tick-blueprint (BlueprintRegistry), tick-atlas (CellMap).
Terrain: forest patches near edges (food source), a lake obstacle, grass default.
Colonists pathfind around water and forage from forest tiles.
Replay proof at tick 200.

Run: uv run --package tick-colony python -m examples.village
"""
from __future__ import annotations

import random as _random_mod
from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext

from tick_spatial import Grid2D, Coord, make_spatial_cleanup_system, pathfind
from tick_schedule import Timer, make_timer_system
from tick_fsm import FSM, FSMGuards, make_fsm_system
from tick_signal import SignalBus
from tick_blueprint import BlueprintRegistry
from tick_atlas import CellDef, CellMap

from tick_colony import (
    Pos2D, NeedSet, NeedHelper, StatBlock, Modifiers,
    Container, ContainedBy,
    EventLog, ColonySnapshot,
    make_need_decay_system, make_modifier_tick_system,
    effective, add_modifier, add_to_container, contents,
    register_colony_components,
)


# ---------------------------------------------------------------------------
# Game-specific component
# ---------------------------------------------------------------------------

@dataclass
class Colonist:
    name: str


@dataclass
class Destination:
    coord: Coord


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRID_W, GRID_H = 20, 20
NUM_COLONISTS = 8
NAMES = ["Ada", "Bjorn", "Cora", "Dax", "Elin", "Finn", "Greta", "Hugo"]

# Stockpile is a fixed entity at the center
STOCKPILE_POS: Coord = (10, 10)

# Action durations (ticks)
FORAGE_TICKS = 6
REST_TICKS = 4
BUILD_TICKS = 10


# ---------------------------------------------------------------------------
# Terrain
# ---------------------------------------------------------------------------

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=2.0, properties={"food": True})
WATER = CellDef(name="water", passable=False)


def _setup_terrain(seed: int) -> None:
    """Populate the cell map with deterministic terrain from seed."""
    rng = _random_mod.Random(seed)
    cells.clear_all()
    # Forest patches near edges — where food grows
    for x in range(GRID_W):
        for y in range(GRID_H):
            edge_dist = min(x, y, GRID_W - 1 - x, GRID_H - 1 - y)
            if edge_dist <= 2 and rng.random() < 0.4:
                cells.set((x, y), FOREST)
    # A small lake blocking the northeast
    cells.fill_rect((14, 3), (17, 6), WATER)
    # Keep stockpile area clear
    cells.set(STOCKPILE_POS, GRASS)


# ---------------------------------------------------------------------------
# Shared state (closure-based DI)
# ---------------------------------------------------------------------------

grid: Grid2D = Grid2D(GRID_W, GRID_H)
cells: CellMap = CellMap(default=GRASS)
event_log = EventLog(max_entries=500)
snapper = ColonySnapshot(grid=grid, event_log=event_log)
bus = SignalBus()
blueprints = BlueprintRegistry()
stockpile_eid: int = -1  # set during setup


# ---------------------------------------------------------------------------
# FSM Guards
# ---------------------------------------------------------------------------

guards = FSMGuards()
guards.register("is_hungry", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "hunger") < 40.0)
guards.register("is_tired", lambda w, eid: NeedHelper.get_value(w.get(eid, NeedSet), "fatigue") < 40.0)
guards.register("timer_done", lambda w, eid: not w.has(eid, Timer))
guards.register("at_stockpile", lambda w, eid: grid.position_of(eid) == STOCKPILE_POS)
guards.register("always", lambda w, eid: True)


# FSM transition table
TRANSITIONS = {
    "idle": [["is_hungry", "foraging"], ["is_tired", "resting"], ["always", "building"]],
    "foraging": [["timer_done", "returning"]],
    "returning": [["at_stockpile", "idle"]],
    "resting": [["timer_done", "idle"]],
    "building": [["timer_done", "idle"]],
}


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def on_timer_fire(world: World, ctx: TickContext, eid: int, timer: Timer) -> None:
    """Handle completed timers (timer already detached)."""
    if not world.alive(eid):
        return
    needs = world.get(eid, NeedSet)
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)

    if timer.name == "forage":
        # Gathered food — hunger restored. Deposit happens when returning to stockpile.
        NeedHelper.set_value(needs, "hunger", NeedHelper.get_value(needs, "hunger") + 30.0)

    elif timer.name == "rest":
        # Restore fatigue
        NeedHelper.set_value(needs, "fatigue", NeedHelper.get_value(needs, "fatigue") + 40.0)
        # Temporary strength boost from being well-rested
        if world.has(eid, Modifiers):
            add_modifier(world.get(eid, Modifiers), "strength", 2.0, duration=20)
        bus.publish("rest_done", tick=ctx.tick_number, colonist=name)

    elif timer.name == "build":
        bus.publish("build_done", tick=ctx.tick_number, colonist=name)


def on_need_critical(world: World, ctx: TickContext, eid: int, need_name: str) -> None:
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
    bus.publish("need_critical", tick=ctx.tick_number, colonist=name, need=need_name)


def on_transition(world: World, ctx: TickContext, eid: int, old_state: str, new_state: str) -> None:
    """Handle FSM state transitions."""
    if new_state == "foraging":
        # Head toward a forest tile (food source)
        forests = cells.of_type("forest")
        if forests:
            target = ctx.random.choice(forests)
        else:
            target = (ctx.random.randint(0, GRID_W - 1), ctx.random.choice([0, GRID_H - 1]))
        world.attach(eid, Destination(coord=target))
        world.attach(eid, Timer(name="forage", remaining=FORAGE_TICKS))

    elif new_state == "returning":
        # Walk back to stockpile to deposit food
        world.attach(eid, Destination(coord=STOCKPILE_POS))

    elif new_state == "resting":
        # Head toward stockpile to rest
        world.attach(eid, Destination(coord=STOCKPILE_POS))
        world.attach(eid, Timer(name="rest", remaining=REST_TICKS))

    elif new_state == "building":
        if world.has(eid, Destination):
            world.detach(eid, Destination)
        world.attach(eid, Timer(name="build", remaining=BUILD_TICKS))

    # Arrived at stockpile after foraging — deposit food
    if old_state == "returning" and new_state == "idle":
        name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
        food = world.spawn()
        if world.has(stockpile_eid, Container):
            add_to_container(world, stockpile_eid, food)
        bus.publish("forage_done", tick=ctx.tick_number,
                    colonist=name, food_stored=len(contents(world, stockpile_eid)))


# ---------------------------------------------------------------------------
# Signal recording
# ---------------------------------------------------------------------------

def record_signal(signal_name: str, data: dict) -> None:
    """Auto-record signals to EventLog."""
    tick = data.get("tick", 0)
    rest = {k: v for k, v in data.items() if k != "tick"}
    event_log.emit(tick=tick, type=signal_name, **rest)


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------

def movement_system(world: World, ctx: TickContext) -> None:
    """Move entities with a Destination toward their target each tick."""
    for eid, (dest, stats, mods) in world.query(Destination, StatBlock, Modifiers):
        pos = grid.position_of(eid)
        if pos is None or pos == dest.coord:
            world.detach(eid, Destination)
            continue
        path = pathfind(grid, pos, dest.coord, cost=cells.move_cost, walkable=cells.passable)
        if path is None or len(path) <= 1:
            world.detach(eid, Destination)
            continue
        speed = max(1, int(effective(stats, mods, "speed")))
        for step in path[1 : speed + 1]:
            grid.move(eid, step)
        # Keep Pos2D in sync for snapshot/restore
        final = grid.position_of(eid)
        if final is not None:
            world.attach(eid, Pos2D(x=float(final[0]), y=float(final[1])))
        if final == dest.coord:
            world.detach(eid, Destination)


def flush_signals(world: World, ctx: TickContext) -> None:
    """Dispatch queued signals."""
    bus.flush()


def census_system(world: World, ctx: TickContext) -> None:
    if ctx.tick_number % 100 != 0:
        return
    colonists = list(world.query(Colonist, NeedSet))
    pop = len(colonists)
    if pop == 0:
        print(f"[tick {ctx.tick_number:>4}]  pop=0")
        return
    avg_hunger = sum(NeedHelper.get_value(ns, "hunger") for _, (_, ns) in colonists) / pop
    avg_fatigue = sum(NeedHelper.get_value(ns, "fatigue") for _, (_, ns) in colonists) / pop
    stored = len(contents(world, stockpile_eid)) if world.alive(stockpile_eid) else 0
    builds = len(event_log.query(type="build_done"))
    print(
        f"[tick {ctx.tick_number:>4}]  pop={pop}  "
        f"avg_hunger={avg_hunger:.1f}  avg_fatigue={avg_fatigue:.1f}  "
        f"stockpile={stored}  builds={builds}"
    )


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_engine(seed: int = 42) -> Engine:
    global stockpile_eid

    engine = Engine(tps=20, seed=seed)
    w = engine.world
    register_colony_components(w)
    w.register_component(Colonist)
    w.register_component(Destination)

    # Generate terrain
    _setup_terrain(seed)

    # Subscribe signals to event log
    for signal in ["forage_done", "rest_done", "build_done", "need_critical"]:
        bus.subscribe(signal, record_signal)

    # Create stockpile
    stockpile_eid = w.spawn()
    w.attach(stockpile_eid, Pos2D(x=float(STOCKPILE_POS[0]), y=float(STOCKPILE_POS[1])))
    w.attach(stockpile_eid, Container(items=[], capacity=100))
    grid.place(stockpile_eid, STOCKPILE_POS)

    # Create colonists (only on passable tiles)
    rng = _random_mod.Random(seed)
    for i in range(NUM_COLONISTS):
        eid = w.spawn()
        w.attach(eid, Colonist(name=NAMES[i]))
        x = 2 + (i * 3) % (GRID_W - 4)
        y = 2 + (i * 5) % (GRID_H - 4)
        # Nudge off impassable tiles
        while not cells.passable((x, y)):
            x = rng.randint(0, GRID_W - 1)
            y = rng.randint(0, GRID_H - 1)
        w.attach(eid, Pos2D(x=float(x), y=float(y)))
        grid.place(eid, (x, y))

        needs = NeedSet(data={})
        NeedHelper.add(needs, "hunger", value=rng.uniform(55.0, 90.0), max_val=100.0,
                       decay_rate=0.5, critical_threshold=15.0)
        NeedHelper.add(needs, "fatigue", value=rng.uniform(65.0, 100.0), max_val=100.0,
                       decay_rate=0.3, critical_threshold=15.0)
        w.attach(eid, needs)

        stats = StatBlock(data={"strength": 8.0 + i % 4, "speed": 2.0 + i % 3})
        mods = Modifiers(entries=[])
        w.attach(eid, stats)
        w.attach(eid, mods)

        # Stagger initial build so colonists desync
        w.attach(eid, FSM(state="building", transitions=TRANSITIONS))
        w.attach(eid, Timer(name="build", remaining=rng.randint(1, BUILD_TICKS)))

    # Register systems (order matters)
    engine.add_system(make_timer_system(on_fire=on_timer_fire))
    engine.add_system(make_fsm_system(guards=guards, on_transition=on_transition))
    engine.add_system(movement_system)
    engine.add_system(make_need_decay_system(on_critical=on_need_critical))
    engine.add_system(make_modifier_tick_system())
    engine.add_system(make_spatial_cleanup_system(grid))
    engine.add_system(flush_signals)
    engine.add_system(census_system)

    return engine


def capture_state(world: World) -> dict:
    """Capture comparable state for replay verification."""
    state = {}
    for eid, (c, ns) in world.query(Colonist, NeedSet):
        state[c.name] = {
            "hunger": round(NeedHelper.get_value(ns, "hunger"), 6),
            "fatigue": round(NeedHelper.get_value(ns, "fatigue"), 6),
            "pos": grid.position_of(eid),
        }
    state["stockpile"] = len(contents(world, stockpile_eid)) if world.alive(stockpile_eid) else 0
    state["events"] = len(event_log)
    return state


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global bus
    seed = 42
    print(f"=== Village demo (seed={seed}) ===\n")

    # --- Run A: straight through to 400 ---
    engine = setup_engine(seed)
    n_forest = len(cells.of_type("forest"))
    n_water = len(cells.of_type("water"))
    print(f"Terrain: {n_forest} forest, {n_water} water, "
          f"{GRID_W * GRID_H - n_forest - n_water} grass\n")
    engine.run(200)
    snap = snapper.snapshot(engine)
    state_at_200 = capture_state(engine.world)
    events_at_200 = len(event_log)

    print(f"\n--- Snapshot taken at tick 200 (events={events_at_200}) ---\n")
    engine.run(200)
    final_a = capture_state(engine.world)
    print(f"\nRun A done (tick 400)")

    # --- Run B: restore from snapshot at 200, continue to 400 ---
    # Reset shared state
    grid._cells.clear()
    grid._entities.clear()
    cells.clear_all()
    event_log.restore([])
    bus = SignalBus()
    for signal in ["forage_done", "rest_done", "build_done", "need_critical"]:
        bus.subscribe(signal, record_signal)

    engine2 = Engine(tps=20, seed=seed)
    register_colony_components(engine2.world)
    engine2.world.register_component(Colonist)
    engine2.world.register_component(Destination)

    _setup_terrain(seed)
    snapper.restore(engine2, snap)

    # Re-add systems (not serialized)
    engine2.add_system(make_timer_system(on_fire=on_timer_fire))
    engine2.add_system(make_fsm_system(guards=guards, on_transition=on_transition))
    engine2.add_system(movement_system)
    engine2.add_system(make_need_decay_system(on_critical=on_need_critical))
    engine2.add_system(make_modifier_tick_system())
    engine2.add_system(make_spatial_cleanup_system(grid))
    engine2.add_system(flush_signals)
    engine2.add_system(census_system)

    events_after_restore = len(event_log)
    print(f"\n--- Restored to tick 200 (events={events_after_restore}) running to 400 ---\n")
    engine2.run(200)
    final_b = capture_state(engine2.world)
    print(f"\nRun B done (tick 400)")

    # --- Verify replay ---
    print("\n--- Replay verification ---")
    match = True
    for name in sorted(set(list(final_a.keys()) + list(final_b.keys()))):
        a_val = final_a.get(name)
        b_val = final_b.get(name)
        if a_val != b_val:
            print(f"  MISMATCH {name}: {a_val} != {b_val}")
            match = False

    if match:
        print("  Replay proof: PASSED (both runs identical)")
    else:
        print("  Replay proof: FAILED")
        raise AssertionError("Replay mismatch")


if __name__ == "__main__":
    main()
