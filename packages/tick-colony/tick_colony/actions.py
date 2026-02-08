from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick import EntityId, TickContext, World


@dataclass
class Action:
    name: str
    total_ticks: int
    elapsed_ticks: int = 0
    cancelled: bool = False


def make_action_system(
    on_complete: Callable[[World, TickContext, int, Action], None],
    on_cancel: Callable[[World, TickContext, int, Action], None] | None = None,
) -> Callable:
    def action_system(world: World, ctx: TickContext) -> None:
        for eid, (action,) in list(world.query(Action)):
            if action.cancelled:
                if on_cancel is not None:
                    on_cancel(world, ctx, eid, action)
                world.detach(eid, Action)
            else:
                action.elapsed_ticks += 1
                if action.elapsed_ticks >= action.total_ticks:
                    on_complete(world, ctx, eid, action)
                    world.detach(eid, Action)
    return action_system
