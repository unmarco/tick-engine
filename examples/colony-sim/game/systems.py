"""Custom systems for the colony simulation."""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.components import Colonist, Destination, VisualPos
from tick_colony import (
    NeedSet, NeedHelper, StatBlock, Modifiers, effective,
    Inventory, InventoryHelper,
    Pos2D, pathfind,
)
from tick_fsm import FSM
from tick_schedule import Timer
from tick_tween import Tween

if TYPE_CHECKING:
    from tick import TickContext, World
    from tick_signal import SignalBus
    from tick_spatial import Grid2D
    from tick_atlas import CellMap


def make_movement_system(grid: Grid2D, cells: CellMap):
    """Return a system that moves colonists along A* paths."""

    def movement_system(world: World, ctx: TickContext) -> None:
        for eid, (dest, stats, mods) in world.query(Destination, StatBlock, Modifiers):
            pos = grid.position_of(eid)
            if pos is None or pos == dest.coord:
                world.detach(eid, Destination)
                continue
            path = pathfind(grid, pos, dest.coord,
                            cost=cells.move_cost, walkable=cells.passable)
            if path is None or len(path) <= 1:
                world.detach(eid, Destination)
                continue
            speed = max(1, int(effective(stats, mods, "speed")))
            for step in path[1: speed + 1]:
                grid.move(eid, step)
            final = grid.position_of(eid)
            if final is not None:
                world.attach(eid, Pos2D(x=float(final[0]), y=float(final[1])))
            if final == dest.coord:
                world.detach(eid, Destination)

    return movement_system


def make_visual_tween_sync_system(grid: Grid2D, tile_size: int):
    """Return a system that spawns Tweens when grid position changes."""
    _last_pos: dict[int, tuple[int, int]] = {}

    def visual_tween_sync_system(world: World, ctx: TickContext) -> None:
        # Track entities with VisualPos
        for eid, (vp, col) in world.query(VisualPos, Colonist):
            pos = grid.position_of(eid)
            if pos is None:
                continue
            prev = _last_pos.get(eid)
            if prev is None:
                # First time — snap to position
                px = pos[0] * tile_size
                py = pos[1] * tile_size
                vp.prev_x = float(px)
                vp.prev_y = float(py)
                vp.curr_x = float(px)
                vp.curr_y = float(py)
                vp.progress = 1.0
                _last_pos[eid] = pos
            elif prev != pos:
                # Position changed — start tween
                vp.prev_x = vp.prev_x + (vp.curr_x - vp.prev_x) * vp.progress
                vp.prev_y = vp.prev_y + (vp.curr_y - vp.prev_y) * vp.progress
                vp.curr_x = float(pos[0] * tile_size)
                vp.curr_y = float(pos[1] * tile_size)
                vp.progress = 0.0
                # Detach any existing tween before attaching new one
                if world.has(eid, Tween):
                    world.detach(eid, Tween)
                world.attach(eid, Tween(
                    target="game.components.VisualPos",
                    field="progress",
                    start_val=0.0,
                    end_val=1.0,
                    duration=3,
                    easing="ease_out",
                ))
                _last_pos[eid] = pos

        # Clean up dead entities
        dead = [eid for eid in _last_pos if not world.alive(eid)]
        for eid in dead:
            del _last_pos[eid]

    return visual_tween_sync_system


def make_birth_system(
    grid: Grid2D, cells: CellMap, stockpile_coord: tuple[int, int],
    stockpile_eid: int, bus: SignalBus, map_size: int,
    name_pool: list[str], tile_size: int,
    transitions: dict,
):
    """Return a system that spawns new colonists."""
    MAX_POP = 20
    BIRTH_FOOD_COST = 5
    BIRTH_FOOD_MIN = 6
    BIRTH_CHANCE = 0.015
    BUILD_TICKS = 10
    _name_idx = [0]

    def birth_system(world: World, ctx: TickContext) -> None:
        alive = len(list(world.query(Colonist)))
        if alive >= MAX_POP:
            return
        if not world.alive(stockpile_eid) or not world.has(stockpile_eid, Inventory):
            return
        stored = InventoryHelper.count(world.get(stockpile_eid, Inventory), "food")
        if stored < BIRTH_FOOD_MIN or ctx.random.random() > BIRTH_CHANCE:
            return
        InventoryHelper.remove(world.get(stockpile_eid, Inventory), "food", BIRTH_FOOD_COST)
        eid = world.spawn()
        nm = name_pool[_name_idx[0] % len(name_pool)]
        _name_idx[0] += 1
        world.attach(eid, Colonist(name=nm))

        # Spawn near stockpile on a passable tile
        x, y = stockpile_coord
        for _ in range(20):
            cx = ctx.random.randint(max(0, x - 2), min(map_size - 1, x + 2))
            cy = ctx.random.randint(max(0, y - 2), min(map_size - 1, y + 2))
            if cells.passable((cx, cy)):
                x, y = cx, cy
                break
        world.attach(eid, Pos2D(x=float(x), y=float(y)))
        grid.place(eid, (x, y))
        ns = NeedSet(data={})
        NeedHelper.add(ns, "hunger", ctx.random.uniform(60.0, 90.0), 100.0, 0.8, 15.0)
        NeedHelper.add(ns, "fatigue", ctx.random.uniform(70.0, 100.0), 100.0, 0.4, 15.0)
        world.attach(eid, ns)
        world.attach(eid, StatBlock(data={"strength": 8.0, "speed": 2.0}))
        world.attach(eid, Modifiers(entries=[]))
        from tick_colony import Lifecycle
        world.attach(eid, Lifecycle(born_tick=ctx.tick_number,
                                    max_age=ctx.random.randint(3000, 5000)))
        world.attach(eid, FSM(state="building", transitions=transitions))
        world.attach(eid, Timer(name="build", remaining=ctx.random.randint(1, BUILD_TICKS)))
        # VisualPos for smooth movement
        px = x * tile_size
        py = y * tile_size
        world.attach(eid, VisualPos(
            prev_x=float(px), prev_y=float(py),
            curr_x=float(px), curr_y=float(py), progress=1.0,
        ))
        bus.publish("birth", name=nm)

    return birth_system


def make_census_system(stockpile_eid: int, bus: SignalBus):
    """Return a system that logs census data periodically."""

    def census_system(world: World, ctx: TickContext) -> None:
        if ctx.tick_number % 500 != 0:
            return
        pop = len(list(world.query(Colonist)))
        food = 0
        if world.alive(stockpile_eid) and world.has(stockpile_eid, Inventory):
            food = InventoryHelper.count(world.get(stockpile_eid, Inventory), "food")
        bus.publish("census", population=pop, food=food)

    return census_system
