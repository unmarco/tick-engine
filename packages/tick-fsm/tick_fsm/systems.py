"""System factory for FSM evaluation."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_fsm.components import FSM
from tick_fsm.guards import FSMGuards

if TYPE_CHECKING:
    from tick import EntityId, TickContext, World


def make_fsm_system(
    guards: FSMGuards,
    on_transition: Callable[[World, TickContext, EntityId, str, str], None] | None = None,
) -> Callable[[World, TickContext], None]:
    """Return a system that evaluates FSM transitions each tick."""

    def fsm_system(world: World, ctx: TickContext) -> None:
        for eid, (fsm,) in list(world.query(FSM)):
            edges = fsm.transitions.get(fsm.state)
            if not edges:
                continue
            for guard_name, target in edges:
                if guards.check(guard_name, world, eid):
                    old = fsm.state
                    fsm.state = target
                    if on_transition is not None:
                        on_transition(world, ctx, eid, old, target)
                    break

    return fsm_system
