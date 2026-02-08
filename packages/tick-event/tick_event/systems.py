"""System factory for world-level event scheduling."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_event.guards import EventGuards
from tick_event.scheduler import EventScheduler

if TYPE_CHECKING:
    from tick import TickContext, World


def make_event_system(
    scheduler: EventScheduler,
    guards: EventGuards,
    on_start: Callable[[World, TickContext, str], None] | None = None,
    on_end: Callable[[World, TickContext, str], None] | None = None,
    on_tick: Callable[[World, TickContext, str, int], None] | None = None,
) -> Callable[[World, TickContext], None]:
    """Return a system that processes world-level events each tick.

    Tick execution order:
    1. Decrement non-cycle active events — end expired ones (on_end)
    2. Tick still-active events (on_tick)
    3. Process cycles — advance phases (on_end for old, on_start for new)
    4. Decrement cooldowns
    5. Evaluate inactive events — check guards, roll probability, activate (on_start)
    """

    def event_system(world: World, ctx: TickContext) -> None:
        # 1. Decrement active events, end expired
        expired: set[str] = set()
        for name, ae in list(scheduler._active.items()):
            ae.remaining -= 1
            if ae.remaining <= 0:
                expired.add(name)

        for name in expired:
            scheduler._deactivate(name)
            if on_end is not None:
                on_end(world, ctx, name)

        # 2. Tick still-active events
        if on_tick is not None:
            for name, ae in scheduler._active.items():
                on_tick(world, ctx, name, ae.remaining)

        # 3. Process cycles
        for cycle_name in list(scheduler._cycle_defs):
            ended, started = scheduler._advance_cycle(cycle_name, ctx.tick_number)
            if ended is not None and on_end is not None:
                on_end(world, ctx, ended)
            if started is not None and on_start is not None:
                on_start(world, ctx, started)

        # 4. Decrement cooldowns
        scheduler._decrement_cooldowns()

        # 5. Evaluate inactive events (definition order)
        # Skip events that just expired this tick (they need at least 1 tick gap)
        for name in scheduler._definition_order:
            if name in expired:
                continue
            if scheduler.is_active(name):
                continue
            if name in scheduler._active:
                continue
            if scheduler._is_on_cooldown(name):
                continue

            defn = scheduler._definitions[name]

            # Check all guard conditions
            all_pass = True
            for guard_name in defn.conditions:
                if not guards.check(guard_name, world, scheduler):
                    all_pass = False
                    break
            if not all_pass:
                continue

            # Roll probability
            if defn.probability < 1.0:
                if ctx.random.random() > defn.probability:
                    continue

            # Activate
            duration = scheduler._resolve_duration(defn, ctx.random)
            scheduler._activate(name, duration, ctx.tick_number)
            if on_start is not None:
                on_start(world, ctx, name)

    return event_system
