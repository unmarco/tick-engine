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
    """Return a system that evaluates FSM transitions each tick.

    Supports hierarchical states via dot-notation.  When no transition
    fires for the current (leaf) state, the system walks up to parent
    states until a transition fires or the root is reached.
    """

    def _parent(state: str) -> str | None:
        dot = state.rfind(".")
        return state[:dot] if dot >= 0 else None

    def _find_transition(
        fsm: FSM, state: str, guards_reg: FSMGuards, world: World, eid: int,
    ) -> str | None:
        current: str | None = state
        while current is not None:
            edges = fsm.transitions.get(current)
            if edges:
                for guard_name, target in edges:
                    if guards_reg.check(guard_name, world, eid):
                        return target
            current = _parent(current)
        return None

    def _resolve_target(target: str, fsm: FSM) -> str:
        state = target
        seen: set[str] = set()
        while state not in seen:
            seen.add(state)
            if state in fsm.history:
                state = fsm.history[state]
            elif state in fsm.initial:
                state = fsm.initial[state]
            else:
                break
        return state

    def _record_history(old_state: str, fsm: FSM) -> None:
        parts = old_state.split(".")
        for i in range(1, len(parts)):
            parent = ".".join(parts[:i])
            child = ".".join(parts[: i + 1])
            fsm.history[parent] = child

    def fsm_system(world: World, ctx: TickContext) -> None:
        for eid, (fsm,) in list(world.query(FSM)):
            target = _find_transition(fsm, fsm.state, guards, world, eid)
            if target is None:
                continue
            old = fsm.state
            _record_history(old, fsm)
            if old.startswith(target + "."):
                # Going up to an ancestor: clear history for the target
                # subtree so _resolve_target uses ``initial`` instead of
                # looping back into the branch we are leaving.
                prefix = target + "."
                for k in [k for k in fsm.history
                          if k == target or k.startswith(prefix)]:
                    del fsm.history[k]
            resolved = _resolve_target(target, fsm)
            fsm.state = resolved
            if on_transition is not None:
                on_transition(world, ctx, eid, old, resolved)

    return fsm_system
