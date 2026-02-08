"""System factories for tick-spatial."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick import World
    from tick_spatial.types import SpatialIndex


def make_spatial_cleanup_system(index: SpatialIndex) -> Callable:
    def spatial_cleanup_system(world: World, ctx: object) -> None:
        dead = [eid for eid in index.tracked_entities() if not world.alive(eid)]
        for eid in dead:
            index.remove(eid)
    return spatial_cleanup_system
