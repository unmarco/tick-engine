"""MoveCommand and handler for player-directed movement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from game.components import Colonist, Destination, SelectedTag
from tick_spatial import Coord

if TYPE_CHECKING:
    from tick import TickContext, World
    from tick_command import CommandQueue
    from tick_signal import SignalBus
    from tick_atlas import CellMap


@dataclass(frozen=True)
class MoveCommand:
    coord: Coord


def make_move_handler(grid, cells: CellMap, bus: SignalBus):
    """Return a handler for MoveCommand that directs the selected colonist."""

    def handle_move(cmd: MoveCommand, world: World, ctx: TickContext) -> bool:
        # Find the selected colonist
        selected = list(world.query(SelectedTag, Colonist))
        if not selected:
            return False
        eid = selected[0][0]

        # Check target is passable
        if not cells.passable(cmd.coord):
            return False

        # Override destination
        world.attach(eid, Destination(coord=cmd.coord))
        nm = world.get(eid, Colonist).name
        bus.publish("command", text=f"{nm} directed to {cmd.coord}")
        return True

    return handle_move
