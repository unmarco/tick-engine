from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick import World
    from tick.types import TickContext


@dataclass
class Lifecycle:
    born_tick: int
    max_age: int  # -1 = immortal


def make_lifecycle_system(
    on_death: Callable[[World, TickContext, int, str], None] | None = None,
) -> Callable[[World, TickContext], None]:
    """Return a system that despawns entities whose age >= max_age.

    The *on_death* callback, if provided, is invoked **before** despawn with
    ``(world, ctx, eid, "old_age")``.  Entities with ``max_age <= 0`` are
    immortal and never expire.
    """

    def lifecycle_system(world: World, ctx: TickContext) -> None:
        for eid, (lc,) in list(world.query(Lifecycle)):
            if lc.max_age > 0 and ctx.tick_number - lc.born_tick >= lc.max_age:
                if on_death is not None:
                    on_death(world, ctx, eid, "old_age")
                world.despawn(eid)

    return lifecycle_system
