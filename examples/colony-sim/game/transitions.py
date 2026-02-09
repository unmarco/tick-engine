"""FSM transitions table and on_transition callback."""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.components import Colonist, Destination
from tick_colony import InventoryHelper, Inventory
from tick_schedule import Timer

if TYPE_CHECKING:
    from tick import TickContext, World
    from tick_signal import SignalBus
    from tick_spatial import Grid2D
    from tick_atlas import CellMap

TRANSITIONS = {
    "idle": [["is_hungry", "foraging"], ["is_tired", "resting"], ["always", "building"]],
    "foraging": [["timer_done", "returning"]],
    "returning": [["at_stockpile", "idle"]],
    "resting": [["timer_done", "idle"]],
    "building": [["timer_done", "idle"]],
}

FORAGE_TICKS = 8
REST_TICKS = 4
BUILD_TICKS = 10


def make_on_transition(
    grid: Grid2D,
    cells: CellMap,
    stockpile_coord: tuple[int, int],
    stockpile_eid: int,
    bus: SignalBus,
    map_size: int,
):
    """Return the FSM transition callback."""

    def on_transition(world: World, ctx: TickContext, eid: int, old: str, new: str) -> None:
        if new == "foraging":
            forests = cells.of_type("forest")
            if forests:
                target = ctx.random.choice(forests)
            else:
                target = (ctx.random.randint(0, map_size - 1),
                          ctx.random.choice([0, map_size - 1]))
            world.attach(eid, Destination(coord=target))
            world.attach(eid, Timer(name="forage", remaining=FORAGE_TICKS))
        elif new == "returning":
            world.attach(eid, Destination(coord=stockpile_coord))
        elif new == "resting":
            world.attach(eid, Destination(coord=stockpile_coord))
            world.attach(eid, Timer(name="rest", remaining=REST_TICKS))
        elif new == "building":
            if world.has(eid, Destination):
                world.detach(eid, Destination)
            world.attach(eid, Timer(name="build", remaining=BUILD_TICKS))

        # Deposit food on return to stockpile
        if old == "returning" and new == "idle":
            nm = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
            if world.alive(stockpile_eid) and world.has(stockpile_eid, Inventory):
                InventoryHelper.add(world.get(stockpile_eid, Inventory), "food", 1)
            bus.publish("food_deposited", colonist=nm)

    return on_transition
