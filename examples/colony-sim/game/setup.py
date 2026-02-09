"""Build the complete game state."""
from __future__ import annotations

import random as _random_mod
from dataclasses import dataclass, field
from typing import Any

from tick import Engine
from tick_colony import (
    register_colony_components,
    Grid2D, Pos2D, make_spatial_cleanup_system,
    make_timer_system, make_fsm_system, make_need_decay_system,
    make_modifier_tick_system, make_lifecycle_system, make_event_system,
    make_command_system, make_ability_system,
    SignalBus, EventScheduler, EventDef, CycleDef,
    CommandQueue, NeedSet, NeedHelper, StatBlock, Modifiers,
    Inventory, InventoryHelper, Lifecycle, AbilityManager,
)
from tick_signal import make_signal_system
from tick_fsm import FSM
from tick_schedule import Timer
from tick_tween import Tween, make_tween_system

from game.abilities import make_ability_callbacks, make_ability_manager
from game.callbacks import make_event_callbacks, make_on_death, make_on_fire, make_on_zero
from game.commands import MoveCommand, make_move_handler
from game.components import Colonist, Destination, SelectedTag, VisualPos
from game.guards import make_ability_guards, make_event_guards, make_fsm_guards
from game.systems import (
    make_birth_system, make_census_system, make_movement_system,
    make_visual_tween_sync_system,
)
from game.terrain import generate_terrain
from game.transitions import TRANSITIONS, make_on_transition

NAMES = ["Ada", "Bjorn", "Cora", "Dax", "Elin", "Finn", "Greta", "Hugo"]
EXTRA_NAMES = ["Ingrid", "Jarl", "Kara", "Leif", "Mira", "Nils", "Olga", "Per",
               "Runa", "Sven", "Tova", "Ulf", "Vera", "Wren", "Ylva", "Zeke"]
BUILD_TICKS = 10


@dataclass
class GameState:
    """Holds all game objects and shared state."""
    engine: Engine
    grid: Grid2D
    cells: Any  # CellMap
    stockpile_coord: tuple[int, int]
    stockpile_eid: int
    bus: SignalBus
    queue: CommandQueue
    ability_mgr: AbilityManager
    sched: EventScheduler
    map_size: int
    tile_size: int
    # UI state
    speed: float = 0.5
    paused: bool = False
    selected_eid: int | None = None
    log_entries: list[tuple[str, tuple[int, int, int]]] = field(default_factory=list)


def build_game(
    seed: int = 42,
    pop: int = 8,
    map_size: int = 20,
    tps: int = 20,
    tile_size: int = 24,
) -> GameState:
    """Wire up the complete game and return GameState."""
    engine = Engine(tps=tps, seed=seed)
    w = engine.world

    # Register all components
    register_colony_components(w)
    w.register_component(Colonist)
    w.register_component(Destination)
    w.register_component(VisualPos)
    w.register_component(SelectedTag)
    w.register_component(Tween)

    # Terrain
    cells, stockpile_coord = generate_terrain(map_size, seed)

    # Grid + stockpile
    grid = Grid2D(map_size, map_size)
    stockpile_eid = w.spawn()
    w.attach(stockpile_eid, Pos2D(x=float(stockpile_coord[0]), y=float(stockpile_coord[1])))
    w.attach(stockpile_eid, Inventory(capacity=60))
    grid.place(stockpile_eid, stockpile_coord)

    # SignalBus
    bus = SignalBus()

    # CommandQueue
    queue = CommandQueue()
    move_handler = make_move_handler(grid, cells, bus)
    queue.handle(MoveCommand, move_handler)

    # AbilityManager
    ability_mgr = make_ability_manager()
    ability_guards = make_ability_guards()

    # EventScheduler
    sched = EventScheduler()
    sched.define_cycle(CycleDef(name="seasons", phases=[
        ("spring", 500), ("summer", 500), ("autumn", 500), ("winter", 500),
    ]))
    sched.define(EventDef("cold_snap", (80, 150), cooldown=200, probability=0.003, conditions=["is_winter"]))
    sched.define(EventDef("heat_wave", (60, 120), cooldown=200, probability=0.002, conditions=["is_summer"]))
    sched.define(EventDef("bountiful_harvest", (100, 200), cooldown=300, probability=0.004, conditions=["is_autumn"]))
    sched.define(EventDef("raid", (30, 60), cooldown=500, probability=0.001))
    sched.define(EventDef("plague", (100, 200), cooldown=1000, probability=0.0004))

    # Guards
    fg = make_fsm_guards(grid, stockpile_coord)
    eg = make_event_guards()

    # Callbacks
    on_fire = make_on_fire(bus)
    on_zero = make_on_zero(bus)
    on_death = make_on_death(bus)
    on_transition = make_on_transition(grid, cells, stockpile_coord, stockpile_eid, bus, map_size)
    ev_start, ev_end, ev_tick = make_event_callbacks(bus, stockpile_eid)
    ab_start, ab_end, ab_tick = make_ability_callbacks(bus, stockpile_eid)

    # Systems (order matters!)
    engine.add_system(make_command_system(queue))                          # 1
    engine.add_system(make_tween_system())                                 # 2
    engine.add_system(make_timer_system(on_fire=on_fire))                  # 3
    engine.add_system(make_fsm_system(guards=fg, on_transition=on_transition))  # 4
    engine.add_system(make_movement_system(grid, cells))                   # 5
    engine.add_system(make_visual_tween_sync_system(grid, tile_size))      # 6
    engine.add_system(make_need_decay_system(on_zero=on_zero))             # 7
    engine.add_system(make_modifier_tick_system())                         # 8
    engine.add_system(make_event_system(sched, eg,
                                        on_start=ev_start, on_end=ev_end, on_tick=ev_tick))  # 9
    engine.add_system(make_ability_system(ability_mgr, ability_guards,
                                          on_start=ab_start, on_end=ab_end, on_tick=ab_tick))  # 10
    engine.add_system(make_lifecycle_system(on_death=on_death))            # 11
    engine.add_system(make_birth_system(
        grid, cells, stockpile_coord, stockpile_eid, bus, map_size,
        EXTRA_NAMES, tile_size, TRANSITIONS,
    ))  # 12
    engine.add_system(make_spatial_cleanup_system(grid))                   # 13
    engine.add_system(make_signal_system(bus))                             # 14

    # Spawn initial colonists
    rng = _random_mod.Random(seed)
    for i in range(min(pop, len(NAMES))):
        eid = w.spawn()
        w.attach(eid, Colonist(name=NAMES[i]))
        x = 2 + (i * 3) % (map_size - 4)
        y = 2 + (i * 5) % (map_size - 4)
        while not cells.passable((x, y)):
            x = rng.randint(0, map_size - 1)
            y = rng.randint(0, map_size - 1)
        w.attach(eid, Pos2D(x=float(x), y=float(y)))
        grid.place(eid, (x, y))
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", rng.uniform(55.0, 90.0), 100.0, 0.8, 15.0)
        NeedHelper.add(ns, "fatigue", rng.uniform(65.0, 100.0), 100.0, 0.4, 15.0)
        w.attach(eid, ns)
        w.attach(eid, StatBlock(data={"strength": 8.0 + i % 4, "speed": 2.0 + i % 3}))
        w.attach(eid, Modifiers(entries=[]))
        w.attach(eid, Lifecycle(born_tick=0, max_age=rng.randint(1500, 2500)))
        w.attach(eid, FSM(state="building", transitions=TRANSITIONS))
        w.attach(eid, Timer(name="build", remaining=rng.randint(1, BUILD_TICKS)))
        # VisualPos for smooth movement
        px = x * tile_size
        py = y * tile_size
        w.attach(eid, VisualPos(
            prev_x=float(px), prev_y=float(py),
            curr_x=float(px), curr_y=float(py), progress=1.0,
        ))

    # Spawn extra colonists if pop > 8
    for i in range(len(NAMES), pop):
        eid = w.spawn()
        nm = EXTRA_NAMES[(i - len(NAMES)) % len(EXTRA_NAMES)]
        w.attach(eid, Colonist(name=nm))
        x = rng.randint(1, map_size - 2)
        y = rng.randint(1, map_size - 2)
        while not cells.passable((x, y)):
            x = rng.randint(0, map_size - 1)
            y = rng.randint(0, map_size - 1)
        w.attach(eid, Pos2D(x=float(x), y=float(y)))
        grid.place(eid, (x, y))
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", rng.uniform(55.0, 90.0), 100.0, 0.8, 15.0)
        NeedHelper.add(ns, "fatigue", rng.uniform(65.0, 100.0), 100.0, 0.4, 15.0)
        w.attach(eid, ns)
        w.attach(eid, StatBlock(data={"strength": 8.0, "speed": 2.0}))
        w.attach(eid, Modifiers(entries=[]))
        w.attach(eid, Lifecycle(born_tick=0, max_age=rng.randint(1500, 2500)))
        w.attach(eid, FSM(state="building", transitions=TRANSITIONS))
        w.attach(eid, Timer(name="build", remaining=rng.randint(1, BUILD_TICKS)))
        px = x * tile_size
        py = y * tile_size
        w.attach(eid, VisualPos(
            prev_x=float(px), prev_y=float(py),
            curr_x=float(px), curr_y=float(py), progress=1.0,
        ))

    return GameState(
        engine=engine,
        grid=grid,
        cells=cells,
        stockpile_coord=stockpile_coord,
        stockpile_eid=stockpile_eid,
        bus=bus,
        queue=queue,
        ability_mgr=ability_mgr,
        sched=sched,
        map_size=map_size,
        tile_size=tile_size,
    )
