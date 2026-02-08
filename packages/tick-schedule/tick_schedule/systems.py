"""System factories for timer and periodic processing."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_schedule.components import Periodic, Timer

if TYPE_CHECKING:
    from tick import EntityId, TickContext, World


def make_timer_system(
    on_fire: Callable[[World, TickContext, int, Timer], None],
) -> Callable:
    """Return a system that decrements Timers and fires callbacks at zero."""

    def timer_system(world: World, ctx: TickContext) -> None:
        for eid, (timer,) in list(world.query(Timer)):
            timer.remaining -= 1
            if timer.remaining <= 0:
                world.detach(eid, Timer)
                on_fire(world, ctx, eid, timer)

    return timer_system


def make_periodic_system(
    on_fire: Callable[[World, TickContext, int, Periodic], None],
) -> Callable:
    """Return a system that increments Periodic elapsed and fires on interval."""

    def periodic_system(world: World, ctx: TickContext) -> None:
        for eid, (periodic,) in list(world.query(Periodic)):
            periodic.elapsed += 1
            if periodic.elapsed >= periodic.interval:
                on_fire(world, ctx, eid, periodic)
                periodic.elapsed = 0

    return periodic_system
