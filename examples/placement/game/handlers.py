"""Command handlers — validation and execution logic."""
from __future__ import annotations

from typing import Any

from tick import World
from tick.types import TickContext
from tick_atlas import CellMap
from tick_blueprint import BlueprintRegistry
from tick_command import CommandQueue, resolve_footprint
from tick_spatial import Grid2D, Pos2D

from game.commands import PlaceStructure, Demolish
from game.components import Structure


def register_handlers(
    queue: CommandQueue,
    blueprints: BlueprintRegistry,
    cellmap: CellMap,
    grid: Grid2D,
    on_place: Any = None,
    on_demolish: Any = None,
    on_reject: Any = None,
) -> None:
    """Wire up PlaceStructure and Demolish handlers on the queue."""

    pos_key = "tick_spatial.types.Pos2D"

    def handle_place(cmd: PlaceStructure, world: World, ctx: TickContext) -> bool:
        # 1. Blueprint exists?
        if not blueprints.has(cmd.name):
            return False

        meta = blueprints.meta(cmd.name)
        origin = (cmd.x, cmd.y)
        footprint_shape = meta.get("footprint", (1, 1))
        terrain_reqs = meta.get("terrain_reqs", {})
        stackable = meta.get("stackable", False)

        # 2. Resolve footprint coords
        coords = resolve_footprint(origin, footprint_shape)

        # 3. Bounds check
        for cx, cy in coords:
            if not (0 <= cx < grid.width and 0 <= cy < grid.height):
                return False

        # 4. Terrain requirements (skip if no requirements)
        if terrain_reqs:
            for coord in coords:
                if not cellmap.matches(coord, terrain_reqs):
                    return False

        # 5. Passability check
        for coord in coords:
            if not cellmap.passable(coord):
                return False

        # 6. Occupancy check (unless stackable)
        if not stackable:
            for coord in coords:
                entities_at = grid.at(coord)
                for eid in entities_at:
                    if world.has(eid, Structure):
                        # Check if the occupying structure is also stackable
                        occ = world.get(eid, Structure)
                        occ_meta = blueprints.meta(occ.name)
                        if not occ_meta.get("stackable", False):
                            return False

        # All checks passed — spawn
        eid = blueprints.spawn(world, cmd.name, overrides={
            pos_key: {"x": cmd.x, "y": cmd.y},
        })
        grid.place(eid, origin)

        if on_place is not None:
            on_place(cmd)
        return True

    def handle_demolish(cmd: Demolish, world: World, ctx: TickContext) -> bool:
        coord = (cmd.x, cmd.y)
        entities = grid.at(coord)
        demolished = False
        for eid in entities:
            if world.has(eid, Structure):
                world.despawn(eid)
                grid.remove(eid)
                demolished = True
        if demolished and on_demolish is not None:
            on_demolish(cmd)
        return demolished

    queue.handle(PlaceStructure, handle_place)
    queue.handle(Demolish, handle_demolish)
