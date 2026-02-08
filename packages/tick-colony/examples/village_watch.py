"""Village Watch — slow-mode educational village demo.

Same simulation as village.py but runs one tick at a time with a
configurable pause between ticks, printing a detailed report each
tick so you can watch the simulation unfold.

Run: uv run python -m examples.village_watch --interval 5 --ticks 50
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass

from tick import Engine, World
from tick.types import TickContext

from tick_colony import (
    Position, Action, NeedSet, NeedHelper, StatBlock, Modifiers,
    Container, ContainedBy,
    Lifecycle, make_lifecycle_system,
    Grid, EventLog,
    make_action_system, make_need_decay_system, make_modifier_tick_system,
    make_grid_cleanup_system,
    effective, add_modifier, add_to_container, remove_from_container, contents,
    register_colony_components,
)


# ---------------------------------------------------------------------------
# Game-specific component
# ---------------------------------------------------------------------------

@dataclass
class Colonist:
    name: str


# ---------------------------------------------------------------------------
# Scenario configuration
# ---------------------------------------------------------------------------

@dataclass
class VillageScenario:
    # World
    grid_width: int
    grid_height: int
    tps: int
    event_log_capacity: int

    # Stockpile
    stockpile_pos: list[int]        # [x, y]
    stockpile_capacity: int

    # Population
    initial_names: list[str]        # determines initial colonist count
    birth_names: list[str]          # names for newborns
    max_population: int

    # Need definitions: [{"name", "max_val", "decay_rate", "critical_threshold"}]
    needs: list[dict]

    # Stat definitions: [{"name", "min", "max"}]
    stats: list[dict]

    # Decision thresholds
    hunger_threshold: float
    fatigue_threshold: float
    forage_ticks: int
    rest_ticks: int

    # Work activities: [{"name", "base_ticks", "stat", "str_w", "spd_w"}]
    activities: list[dict]

    # Lifecycle
    max_age_min: int                # -1 = immortal
    max_age_max: int

    # Birth config
    birth_mode: str                 # "stockpile" | "periodic" | "none"
    birth_food_cost: int
    birth_food_threshold: int
    birth_interval: int
    birth_avg_hunger_min: float
    birth_chance: float


DEFAULT_SCENARIO = VillageScenario(
    grid_width=20,
    grid_height=20,
    tps=20,
    event_log_capacity=500,
    stockpile_pos=[10, 10],
    stockpile_capacity=100,
    initial_names=["Ada", "Bjorn", "Cora", "Dax", "Elin", "Finn", "Greta", "Hugo"],
    birth_names=["Ivy", "Jace", "Kira", "Leo", "Mira", "Nils", "Opal", "Pax",
                 "Quinn", "Rune", "Sage", "Tove", "Una", "Voss", "Wren", "Xan"],
    max_population=20,
    needs=[
        {"name": "hunger", "max_val": 100.0, "decay_rate": 0.5, "critical_threshold": 15.0},
        {"name": "fatigue", "max_val": 100.0, "decay_rate": 0.3, "critical_threshold": 15.0},
    ],
    stats=[
        {"name": "strength", "min": 6.0, "max": 12.0},
        {"name": "speed", "min": 1.0, "max": 5.0},
    ],
    hunger_threshold=40.0,
    fatigue_threshold=40.0,
    forage_ticks=6,
    rest_ticks=4,
    activities=[
        {"name": "build",  "base_ticks": 12, "stat": "strength", "str_w": 3, "spd_w": 1},
        {"name": "craft",  "base_ticks": 8,  "stat": "speed",    "str_w": 1, "spd_w": 3},
        {"name": "patrol", "base_ticks": 8,  "stat": "speed",    "str_w": 1, "spd_w": 2},
        {"name": "train",  "base_ticks": 6,  "stat": "strength", "str_w": 2, "spd_w": 1},
    ],
    max_age_min=800,
    max_age_max=1200,
    birth_mode="stockpile",
    birth_food_cost=5,
    birth_food_threshold=10,
    birth_interval=50,
    birth_avg_hunger_min=60.0,
    birth_chance=0.5,
)


# ---------------------------------------------------------------------------
# Shared state (initialized in setup_engine from scenario)
# ---------------------------------------------------------------------------

grid: Grid = None  # type: ignore
event_log: EventLog = None  # type: ignore
stockpile_eid: int = -1
scenario: VillageScenario = DEFAULT_SCENARIO
birth_counter: list[int] = [0]
death_counter: list[int] = [0]
peak_population: list[int] = [0]


# ---------------------------------------------------------------------------
# Name generation
# ---------------------------------------------------------------------------

def _next_name(ctx_random) -> str:
    """Generate a name for a newborn colonist."""
    names = scenario.birth_names
    idx = birth_counter[0] % len(names)
    generation = birth_counter[0] // len(names)
    name = names[idx]
    if generation > 0:
        name = f"{name} {_roman(generation + 1)}"
    return name


def _roman(n: int) -> str:
    """Simple roman numerals for small numbers."""
    if n <= 0:
        return str(n)
    numerals = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'),
                (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'),
                (5, 'V'), (4, 'IV'), (1, 'I')]
    result = []
    for value, symbol in numerals:
        while n >= value:
            result.append(symbol)
            n -= value
    return ''.join(result)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def on_action_complete(world: World, ctx: TickContext, eid: int, action: Action) -> None:
    if not world.alive(eid):
        return
    needs = world.get(eid, NeedSet)
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)

    if action.name == "forage":
        NeedHelper.set_value(needs, "hunger", NeedHelper.get_value(needs, "hunger") + 30.0)
        sp = scenario.stockpile_pos
        grid.move(eid, sp[0], sp[1])
        food = world.spawn()
        if world.has(stockpile_eid, Container):
            add_to_container(world, stockpile_eid, food)
        event_log.emit(tick=ctx.tick_number, type="forage_done",
                       colonist=name, food_stored=len(contents(world, stockpile_eid)))

    elif action.name == "rest":
        NeedHelper.set_value(needs, "fatigue", NeedHelper.get_value(needs, "fatigue") + 40.0)
        if world.has(eid, Modifiers):
            add_modifier(world.get(eid, Modifiers), "strength", 2.0, duration=20)
        event_log.emit(tick=ctx.tick_number, type="rest_done", colonist=name)

    elif action.name == "build":
        fatigue = NeedHelper.get_value(needs, "fatigue")
        NeedHelper.set_value(needs, "fatigue", fatigue - 5.0)
        event_log.emit(tick=ctx.tick_number, type="build_done", colonist=name)

    elif action.name == "craft":
        hunger = NeedHelper.get_value(needs, "hunger")
        NeedHelper.set_value(needs, "hunger", hunger - 3.0)
        item = world.spawn()
        if world.has(stockpile_eid, Container):
            add_to_container(world, stockpile_eid, item)
        event_log.emit(tick=ctx.tick_number, type="craft_done",
                       colonist=name, stockpile=len(contents(world, stockpile_eid)))

    elif action.name == "patrol":
        hunger = NeedHelper.get_value(needs, "hunger")
        fatigue = NeedHelper.get_value(needs, "fatigue")
        NeedHelper.set_value(needs, "hunger", hunger - 3.0)
        NeedHelper.set_value(needs, "fatigue", fatigue - 3.0)
        tx = ctx.random.randint(0, scenario.grid_width - 1)
        ty = ctx.random.randint(0, scenario.grid_height - 1)
        grid.move(eid, tx, ty)
        event_log.emit(tick=ctx.tick_number, type="patrol_done", colonist=name)

    elif action.name == "train":
        fatigue = NeedHelper.get_value(needs, "fatigue")
        NeedHelper.set_value(needs, "fatigue", fatigue - 8.0)
        if world.has(eid, Modifiers):
            add_modifier(world.get(eid, Modifiers), "speed", 1.5, duration=25)
        event_log.emit(tick=ctx.tick_number, type="train_done", colonist=name)


def on_need_critical(world: World, ctx: TickContext, eid: int, need_name: str) -> None:
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
    event_log.emit(tick=ctx.tick_number, type="need_critical",
                   colonist=name, need=need_name)


def on_need_zero(world: World, ctx: TickContext, eid: int, need_name: str) -> None:
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
    grid.remove(eid)
    event_log.emit(tick=ctx.tick_number, type="death", colonist=name,
                   cause=f"{need_name} depleted")
    death_counter[0] += 1
    world.despawn(eid)


def on_lifecycle_death(world: World, ctx: TickContext, eid: int, cause: str) -> None:
    name = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
    grid.remove(eid)
    event_log.emit(tick=ctx.tick_number, type="death", colonist=name, cause="old age")
    death_counter[0] += 1


# ---------------------------------------------------------------------------
# Decision system
# ---------------------------------------------------------------------------

def decision_system(world: World, ctx: TickContext) -> None:
    for eid, (colonist, needs, stats) in world.query(Colonist, NeedSet, StatBlock):
        if world.has(eid, Action):
            continue

        hunger = NeedHelper.get_value(needs, "hunger")
        fatigue = NeedHelper.get_value(needs, "fatigue")
        mods = world.get(eid, Modifiers) if world.has(eid, Modifiers) else Modifiers(entries=[])
        speed = effective(stats, mods, "speed")
        strength = effective(stats, mods, "strength")

        if hunger < scenario.hunger_threshold:
            tx = ctx.random.randint(0, scenario.grid_width - 1)
            ty = ctx.random.choice([0, scenario.grid_height - 1])
            _move_toward(eid, tx, ty, speed, ctx)
            world.attach(eid, Action(name="forage", total_ticks=scenario.forage_ticks))
            event_log.emit(tick=ctx.tick_number, type="decision",
                           colonist=colonist.name, action="forage",
                           reason=f"hunger low ({hunger:.0f})")
        elif fatigue < scenario.fatigue_threshold:
            sp = scenario.stockpile_pos
            _move_toward(eid, sp[0], sp[1], speed, ctx)
            world.attach(eid, Action(name="rest", total_ticks=scenario.rest_ticks))
            event_log.emit(tick=ctx.tick_number, type="decision",
                           colonist=colonist.name, action="rest",
                           reason=f"fatigue low ({fatigue:.0f})")
        else:
            activities = scenario.activities
            weights = [
                a["str_w"] * strength + a["spd_w"] * speed
                for a in activities
            ]
            chosen = ctx.random.choices(activities, weights=weights, k=1)[0]
            stat_val = effective(stats, mods, chosen["stat"])
            duration = max(chosen["base_ticks"] - 4, chosen["base_ticks"] - int(stat_val))
            world.attach(eid, Action(name=chosen["name"], total_ticks=duration))
            event_log.emit(tick=ctx.tick_number, type="decision",
                           colonist=colonist.name, action=chosen["name"],
                           reason=f"chose {chosen['name']} (str {strength:.0f}, spd {speed:.0f})")


def _move_toward(eid: int, tx: int, ty: int, speed: float, ctx: TickContext) -> None:
    pos = grid.position_of(eid)
    if pos is None:
        return
    x, y = pos
    steps = max(1, int(speed))
    for _ in range(steps):
        dx = 1 if tx > x else (-1 if tx < x else 0)
        dy = 1 if ty > y else (-1 if ty < y else 0)
        nx, ny = x + dx, y + dy
        nx = max(0, min(scenario.grid_width - 1, nx))
        ny = max(0, min(scenario.grid_height - 1, ny))
        if (nx, ny) != (x, y):
            grid.move(eid, nx, ny)
            x, y = nx, ny


# ---------------------------------------------------------------------------
# Birth system
# ---------------------------------------------------------------------------

def birth_system(world: World, ctx: TickContext) -> None:
    pop = sum(1 for _ in world.query(Colonist, NeedSet))
    if pop > peak_population[0]:
        peak_population[0] = pop
    if pop >= scenario.max_population:
        return

    should_birth = False

    if scenario.birth_mode == "stockpile":
        if world.alive(stockpile_eid) and world.has(stockpile_eid, Container):
            stored = len(contents(world, stockpile_eid))
            if stored >= scenario.birth_food_threshold:
                should_birth = True

    elif scenario.birth_mode == "periodic":
        if ctx.tick_number % scenario.birth_interval == 0:
            hungers = []
            for _, (_, ns) in world.query(Colonist, NeedSet):
                if "hunger" in ns.data:
                    hungers.append(NeedHelper.get_value(ns, "hunger"))
            if hungers and (sum(hungers) / len(hungers)) > scenario.birth_avg_hunger_min:
                if ctx.random.random() < scenario.birth_chance:
                    should_birth = True

    if should_birth:
        _spawn_colonist(world, ctx)


def _spawn_colonist(world: World, ctx: TickContext) -> None:
    """Spawn a new colonist from scenario config."""
    # Consume food if stockpile mode
    if scenario.birth_mode == "stockpile":
        container = world.get(stockpile_eid, Container)
        for _ in range(min(scenario.birth_food_cost, len(container.items))):
            food_eid = container.items.pop()
            if world.has(food_eid, ContainedBy):
                world.detach(food_eid, ContainedBy)
            world.despawn(food_eid)

    name = _next_name(ctx.random)
    birth_counter[0] += 1

    eid = world.spawn()
    world.attach(eid, Colonist(name=name))

    # Position near stockpile
    sp = scenario.stockpile_pos
    x = max(0, min(scenario.grid_width - 1, sp[0] + ctx.random.randint(-2, 2)))
    y = max(0, min(scenario.grid_height - 1, sp[1] + ctx.random.randint(-2, 2)))
    world.attach(eid, Position(x=x, y=y))
    grid.place(eid, x, y)

    # Needs at max
    needs = NeedSet(data={})
    for nd in scenario.needs:
        NeedHelper.add(needs, nd["name"], value=nd["max_val"],
                       max_val=nd["max_val"], decay_rate=nd["decay_rate"],
                       critical_threshold=nd["critical_threshold"])
    world.attach(eid, needs)

    # Random stats in range
    stats_data = {}
    for sd in scenario.stats:
        stats_data[sd["name"]] = sd["min"] + ctx.random.random() * (sd["max"] - sd["min"])
    world.attach(eid, StatBlock(data=stats_data))
    world.attach(eid, Modifiers(entries=[]))

    # Lifecycle
    if scenario.max_age_min > 0 and scenario.max_age_max > 0:
        max_age = ctx.random.randint(scenario.max_age_min, scenario.max_age_max)
    else:
        max_age = -1
    world.attach(eid, Lifecycle(born_tick=ctx.tick_number, max_age=max_age))

    event_log.emit(tick=ctx.tick_number, type="birth", colonist=name)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def progress_bar(elapsed: int, total: int, width: int = 10) -> str:
    filled = round(width * elapsed / total) if total > 0 else 0
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def narrate_event(event) -> str:
    d = event.data
    if event.type == "birth":
        return f"{d['colonist']} was born!"
    if event.type == "death":
        return f"{d['colonist']} died ({d['cause']})"
    if event.type == "decision":
        return f"{d['colonist']} decided to {d['action']} ({d['reason']})"
    if event.type == "forage_done":
        return f"{d['colonist']} finished foraging (stockpile: {d['food_stored']} items)"
    if event.type == "rest_done":
        return f"{d['colonist']} finished resting"
    if event.type == "build_done":
        return f"{d['colonist']} finished building"
    if event.type == "craft_done":
        return f"{d['colonist']} finished crafting (stockpile: {d['stockpile']} items)"
    if event.type == "patrol_done":
        return f"{d['colonist']} finished patrolling"
    if event.type == "train_done":
        return f"{d['colonist']} finished training"
    if event.type == "need_critical":
        return f"{d['colonist']}'s {d['need']} is critical!"
    return f"{event.type}: {d}"


def format_elapsed(seconds: float) -> str:
    m = int(seconds) // 60
    s = seconds - m * 60
    if m > 0:
        return f"{m}m {s:.1f}s"
    return f"{s:.1f}s"


def print_report(world: World, tick: int, event_log: EventLog,
                 grid: Grid, stockpile_eid: int, dt: float) -> None:
    elapsed = tick * dt
    print(f"\n=== TICK {tick} === (elapsed: {format_elapsed(elapsed)})\n")

    # -- Colonists --
    print("  COLONISTS")
    for eid, (col, needs) in world.query(Colonist, NeedSet):
        pos = grid.position_of(eid)
        pos_str = f"({pos[0]:>2},{pos[1]:>2})" if pos else "(?,?)"

        if world.has(eid, Action):
            action = world.get(eid, Action)
            bar = progress_bar(action.elapsed_ticks, action.total_ticks)
            action_str = f"{action.name:<10}{bar} {action.elapsed_ticks}/{action.total_ticks}"
        else:
            action_str = "idle"

        need_parts = []
        for name in NeedHelper.names(needs):
            entry = needs.data[name]
            val, max_val = entry[0], entry[1]
            need_parts.append(f"{name}: {val:.1f}/{max_val:.0f}")

        mod_str = ""
        if world.has(eid, Modifiers):
            mods = world.get(eid, Modifiers)
            mod_tags = []
            for entry in mods.entries:
                sign = "+" if entry[1] >= 0 else ""
                mod_tags.append(f"[{sign}{entry[1]:.1f} {entry[0]} {entry[2]}t]")
            if mod_tags:
                mod_str = "  " + " ".join(mod_tags)

        age_str = ""
        if world.has(eid, Lifecycle):
            lc = world.get(eid, Lifecycle)
            age = tick - lc.born_tick
            age_str = f"  age:{age}"

        needs_str = "  ".join(need_parts)
        padding = " " * max(0, 42 - len(action_str))
        print(f"  {col.name:<12}{pos_str}  {action_str}{padding}{needs_str}{mod_str}{age_str}")

    # -- Events this tick --
    tick_events = event_log.query(after=tick - 1, before=tick + 1)
    if tick_events:
        print(f"\n  EVENTS")
        for ev in tick_events:
            print(f"  > {narrate_event(ev)}")

    # -- Summary --
    pop = sum(1 for _ in world.query(Colonist, NeedSet))
    stored = len(contents(world, stockpile_eid)) if world.alive(stockpile_eid) else 0
    cap = world.get(stockpile_eid, Container).capacity if world.has(stockpile_eid, Container) else 0
    print(f"\n  SUMMARY  pop: {pop}  stockpile: {stored}/{cap}  total events: {len(event_log)}")


def print_summary(world: World, engine: Engine, event_log: EventLog,
                  grid: Grid, stockpile_eid: int) -> None:
    tick = engine.clock.tick_number
    pop = sum(1 for _ in world.query(Colonist, NeedSet))
    births = birth_counter[0]
    deaths = death_counter[0]
    stored = len(contents(world, stockpile_eid)) if world.alive(stockpile_eid) else 0

    print(f"\n=== SIMULATION SUMMARY (tick {tick}) ===")
    print(f"  Population:    {pop} / {scenario.max_population}")
    print(f"  Total births:  {births}")
    print(f"  Total deaths:  {deaths}")
    print(f"  Stockpile:     {stored}")
    print(f"  Peak pop:      {peak_population[0]}")
    print(f"  Total events:  {len(event_log)}")

    # List surviving colonists
    if pop > 0:
        print(f"\n  SURVIVORS")
        for eid, (col, ns) in world.query(Colonist, NeedSet):
            hunger = NeedHelper.get_value(ns, "hunger")
            fatigue = NeedHelper.get_value(ns, "fatigue")
            lc = world.get(eid, Lifecycle) if world.has(eid, Lifecycle) else None
            age = tick - lc.born_tick if lc else "?"
            print(f"    {col.name:<12} age: {age:<6} hunger: {hunger:.0f}  fatigue: {fatigue:.0f}")


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def setup_engine(scn: VillageScenario, seed: int = 42) -> Engine:
    global stockpile_eid, grid, event_log, scenario, birth_counter, death_counter, peak_population

    scenario = scn
    grid = Grid(scn.grid_width, scn.grid_height)
    event_log = EventLog(max_entries=scn.event_log_capacity)
    birth_counter = [0]
    death_counter = [0]
    peak_population = [len(scn.initial_names)]

    engine = Engine(tps=scn.tps, seed=seed)
    w = engine.world
    register_colony_components(w)
    w.register_component(Colonist)

    # Stockpile
    stockpile_eid = w.spawn()
    w.attach(stockpile_eid, Position(x=scn.stockpile_pos[0], y=scn.stockpile_pos[1]))
    w.attach(stockpile_eid, Container(items=[], capacity=scn.stockpile_capacity))
    grid.place(stockpile_eid, scn.stockpile_pos[0], scn.stockpile_pos[1])

    # Colonists -- staggered initial values for variety
    for i, name in enumerate(scn.initial_names):
        eid = w.spawn()
        w.attach(eid, Colonist(name=name))
        x = 2 + (i * 3) % (scn.grid_width - 4)
        y = 2 + (i * 5) % (scn.grid_height - 4)
        w.attach(eid, Position(x=x, y=y))
        grid.place(eid, x, y)

        needs = NeedSet(data={})
        for j, nd in enumerate(scn.needs):
            # Stagger: first need starts at 65+i*5, second at 75+i*3, etc.
            base_offsets = [65.0, 75.0]
            stagger_rates = [5.0, 3.0]
            base = base_offsets[j] if j < len(base_offsets) else nd["max_val"] * 0.7
            rate = stagger_rates[j] if j < len(stagger_rates) else 2.0
            initial = min(base + i * rate, nd["max_val"])
            NeedHelper.add(needs, nd["name"], value=initial,
                           max_val=nd["max_val"], decay_rate=nd["decay_rate"],
                           critical_threshold=nd["critical_threshold"])
        w.attach(eid, needs)

        # Stats: stagger using index modulo for variety
        stats_data = {}
        for k, sd in enumerate(scn.stats):
            spread = sd["max"] - sd["min"]
            stats_data[sd["name"]] = sd["min"] + (i % max(1, int(spread))) * 1.0
        w.attach(eid, StatBlock(data=stats_data))
        w.attach(eid, Modifiers(entries=[]))

        # Lifecycle
        if scn.max_age_min > 0 and scn.max_age_max > 0:
            # Use a deterministic spread for initial colonists
            age_range = scn.max_age_max - scn.max_age_min
            max_age = scn.max_age_min + (i * age_range // max(1, len(scn.initial_names) - 1))
        else:
            max_age = -1
        w.attach(eid, Lifecycle(born_tick=0, max_age=max_age))

    # Systems in order
    engine.add_system(decision_system)
    engine.add_system(birth_system)
    engine.add_system(make_action_system(on_complete=on_action_complete))
    engine.add_system(make_need_decay_system(on_critical=on_need_critical, on_zero=on_need_zero))
    engine.add_system(make_lifecycle_system(on_death=on_lifecycle_death))
    engine.add_system(make_modifier_tick_system())
    engine.add_system(make_grid_cleanup_system(grid))

    return engine


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Village Watch — slow-mode village demo")
    parser.add_argument("--interval", "-i", type=float, default=5,
                        help="seconds between ticks (default: 5)")
    parser.add_argument("--ticks", "-n", type=int, default=100,
                        help="total ticks to simulate (default: 100)")
    parser.add_argument("--seed", "-s", type=int, default=42,
                        help="RNG seed (default: 42)")
    parser.add_argument("--clear", action="store_true",
                        help="clear terminal between ticks for live dashboard feel")
    parser.add_argument("--step", action="store_true",
                        help="step mode: press Enter to advance, q to quit")
    parser.add_argument("--headless", action="store_true",
                        help="suppress tick-by-tick output; print summary at end")
    args = parser.parse_args()

    if not args.headless:
        print(f"=== Village Watch (seed={args.seed}, ticks={args.ticks}, "
              f"interval={args.interval}s) ===")

    engine = setup_engine(DEFAULT_SCENARIO, args.seed)
    dt = engine.clock.dt

    try:
        for i in range(args.ticks):
            engine.step()
            tick = engine.clock.tick_number
            if not args.headless:
                if args.clear:
                    print("\033[2J\033[H", end="")
                print_report(engine.world, tick, event_log, grid, stockpile_eid, dt)
                if i < args.ticks - 1:
                    if args.step:
                        cmd = input("  [Enter=next, q=quit] ")
                        if cmd.strip().lower() == "q":
                            break
                    else:
                        time.sleep(args.interval)
    except KeyboardInterrupt:
        if not args.headless:
            print(f"\n\nStopped at tick {engine.clock.tick_number}. Goodbye.")

    if args.headless:
        print_summary(engine.world, engine, event_log, grid, stockpile_eid)


if __name__ == "__main__":
    main()
