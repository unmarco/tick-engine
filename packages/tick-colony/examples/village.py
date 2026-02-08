"""Village demo — exercises all 6 colony primitives.

20x20 grid, 8 colonists with hunger/fatigue needs, strength/speed stats.
Systems: need decay, modifier tick, decision, action progress, movement,
census every 100 ticks. Stockpile as container. Event log.
Replay proof at tick 200.

Run: uv run python -m examples.village
"""
from __future__ import annotations

from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext

from tick_colony import (
    Position, Action, NeedSet, NeedHelper, StatBlock, Modifiers,
    Container, ContainedBy,
    Grid, EventLog, ColonySnapshot,
    make_action_system, make_need_decay_system, make_modifier_tick_system,
    make_grid_cleanup_system,
    effective, add_modifier, add_to_container, contents,
    register_colony_components,
)


# ---------------------------------------------------------------------------
# Game-specific component
# ---------------------------------------------------------------------------

@dataclass
class Colonist:
    name: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GRID_W, GRID_H = 20, 20
NUM_COLONISTS = 8
NAMES = ["Ada", "Bjorn", "Cora", "Dax", "Elin", "Finn", "Greta", "Hugo"]

# Stockpile is a fixed entity at the center
STOCKPILE_POS = (10, 10)

# Action durations (ticks)
FORAGE_TICKS = 6
REST_TICKS = 4
BUILD_TICKS = 10


# ---------------------------------------------------------------------------
# Shared state (closure-based DI)
# ---------------------------------------------------------------------------

grid = Grid(GRID_W, GRID_H)
event_log = EventLog(max_entries=500)
snapper = ColonySnapshot(grid=grid, event_log=event_log)
stockpile_eid: int = -1  # set during setup


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def on_action_complete(world: World, ctx: TickContext, eid: int, action: Action) -> None:
    """Handle completed actions."""
    if not world.alive(eid):
        return
    needs = world.get(eid, NeedSet)
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)

    if action.name == "forage":
        # Restore hunger, deposit food in stockpile
        NeedHelper.set_value(needs, "hunger", NeedHelper.get_value(needs, "hunger") + 30.0)
        # Move to stockpile and deposit
        grid.move(eid, *STOCKPILE_POS)
        food = world.spawn()
        if world.has(stockpile_eid, Container):
            add_to_container(world, stockpile_eid, food)
        event_log.emit(tick=ctx.tick_number, type="forage_done",
                       colonist=name, food_stored=len(contents(world, stockpile_eid)))

    elif action.name == "rest":
        # Restore fatigue
        NeedHelper.set_value(needs, "fatigue", NeedHelper.get_value(needs, "fatigue") + 40.0)
        # Temporary strength boost from being well-rested
        if world.has(eid, Modifiers):
            add_modifier(world.get(eid, Modifiers), "strength", 2.0, duration=20)
        event_log.emit(tick=ctx.tick_number, type="rest_done", colonist=name)

    elif action.name == "build":
        event_log.emit(tick=ctx.tick_number, type="build_done", colonist=name)


def on_need_critical(world: World, ctx: TickContext, eid: int, need_name: str) -> None:
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
    event_log.emit(tick=ctx.tick_number, type="need_critical",
                   colonist=name, need=need_name)


# ---------------------------------------------------------------------------
# Decision system — assigns actions based on needs
# ---------------------------------------------------------------------------

def decision_system(world: World, ctx: TickContext) -> None:
    """Idle colonists choose: forage if hungry, rest if tired, build otherwise."""
    for eid, (colonist, needs, stats) in world.query(Colonist, NeedSet, StatBlock):
        if world.has(eid, Action):
            continue  # busy

        hunger = NeedHelper.get_value(needs, "hunger")
        fatigue = NeedHelper.get_value(needs, "fatigue")
        mods = world.get(eid, Modifiers) if world.has(eid, Modifiers) else Modifiers(entries=[])
        speed = effective(stats, mods, "speed")

        if hunger < 40.0:
            # Go forage — move to a random edge tile
            tx = ctx.random.randint(0, GRID_W - 1)
            ty = ctx.random.choice([0, GRID_H - 1])
            _move_toward(eid, tx, ty, speed, ctx)
            world.attach(eid, Action(name="forage", total_ticks=FORAGE_TICKS))

        elif fatigue < 40.0:
            # Go rest — move toward center
            _move_toward(eid, STOCKPILE_POS[0], STOCKPILE_POS[1], speed, ctx)
            world.attach(eid, Action(name="rest", total_ticks=REST_TICKS))

        else:
            # Build — stay put
            world.attach(eid, Action(name="build", total_ticks=BUILD_TICKS))


def _move_toward(eid: int, tx: int, ty: int, speed: float, ctx: TickContext) -> None:
    """Move entity a few steps toward target (simple, no pathfinding)."""
    pos = grid.position_of(eid)
    if pos is None:
        return
    x, y = pos
    steps = max(1, int(speed))
    for _ in range(steps):
        dx = 1 if tx > x else (-1 if tx < x else 0)
        dy = 1 if ty > y else (-1 if ty < y else 0)
        nx, ny = x + dx, y + dy
        nx = max(0, min(GRID_W - 1, nx))
        ny = max(0, min(GRID_H - 1, ny))
        if (nx, ny) != (x, y):
            grid.move(eid, nx, ny)
            x, y = nx, ny


# ---------------------------------------------------------------------------
# Census system
# ---------------------------------------------------------------------------

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

    # Create stockpile
    stockpile_eid = w.spawn()
    w.attach(stockpile_eid, Position(x=STOCKPILE_POS[0], y=STOCKPILE_POS[1]))
    w.attach(stockpile_eid, Container(items=[], capacity=100))
    grid.place(stockpile_eid, *STOCKPILE_POS)

    # Create colonists
    for i in range(NUM_COLONISTS):
        eid = w.spawn()
        w.attach(eid, Colonist(name=NAMES[i]))
        x = 2 + (i * 3) % (GRID_W - 4)
        y = 2 + (i * 5) % (GRID_H - 4)
        w.attach(eid, Position(x=x, y=y))
        grid.place(eid, x, y)

        needs = NeedSet(data={})
        NeedHelper.add(needs, "hunger", value=80.0, max_val=100.0,
                       decay_rate=0.5, critical_threshold=15.0)
        NeedHelper.add(needs, "fatigue", value=90.0, max_val=100.0,
                       decay_rate=0.3, critical_threshold=15.0)
        w.attach(eid, needs)

        stats = StatBlock(data={"strength": 8.0 + i % 4, "speed": 2.0 + i % 3})
        mods = Modifiers(entries=[])
        w.attach(eid, stats)
        w.attach(eid, mods)

    # Register systems (order matters)
    engine.add_system(decision_system)
    engine.add_system(make_action_system(on_complete=on_action_complete))
    engine.add_system(make_need_decay_system(on_critical=on_need_critical))
    engine.add_system(make_modifier_tick_system())
    engine.add_system(make_grid_cleanup_system(grid))
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
    seed = 42
    print(f"=== Village demo (seed={seed}) ===\n")

    # --- Run A: straight through to 400 ---
    engine = setup_engine(seed)
    engine.run(200)
    snap = snapper.snapshot(engine)
    state_at_200 = capture_state(engine.world)
    events_at_200 = len(event_log)

    print(f"\n--- Snapshot taken at tick 200 ---\n")
    engine.run(200)
    final_a = capture_state(engine.world)
    print(f"\nRun A done (tick 400)")

    # --- Run B: restore from snapshot at 200, continue to 400 ---
    # Reset shared state
    grid._cells.clear()
    grid._entities.clear()
    event_log.restore([])

    engine2 = Engine(tps=20, seed=seed)
    register_colony_components(engine2.world)
    engine2.world.register_component(Colonist)

    snapper.restore(engine2, snap)

    # Re-add systems (not serialized)
    engine2.add_system(decision_system)
    engine2.add_system(make_action_system(on_complete=on_action_complete))
    engine2.add_system(make_need_decay_system(on_critical=on_need_critical))
    engine2.add_system(make_modifier_tick_system())
    engine2.add_system(make_grid_cleanup_system(grid))
    engine2.add_system(census_system)

    print(f"\n--- Restored to tick 200, running to 400 ---\n")
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
