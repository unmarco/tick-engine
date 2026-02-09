"""System factory for the command queue."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from tick_command.queue import CommandQueue

if TYPE_CHECKING:
    from tick import TickContext, World


def make_command_system(
    queue: CommandQueue,
    on_accept: Callable[[Any], None] | None = None,
    on_reject: Callable[[Any], None] | None = None,
) -> Callable[[World, TickContext], None]:
    """Return a system that drains the command queue each tick.

    ``on_accept(cmd)`` fires after a handler returns True.
    ``on_reject(cmd)`` fires after a handler returns False.
    """

    def command_system(world: World, ctx: TickContext) -> None:
        results = queue.drain(world, ctx)
        for cmd, accepted in results:
            if accepted:
                if on_accept is not None:
                    on_accept(cmd)
            else:
                if on_reject is not None:
                    on_reject(cmd)

    return command_system
