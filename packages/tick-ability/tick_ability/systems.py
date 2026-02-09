"""System factory for player-triggered abilities."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tick_ability.guards import AbilityGuards
from tick_ability.manager import AbilityManager

if TYPE_CHECKING:
    from tick import TickContext, World


def make_ability_system(
    manager: AbilityManager,
    guards: AbilityGuards | None = None,
    on_start: Callable[[World, TickContext, str], None] | None = None,
    on_end: Callable[[World, TickContext, str], None] | None = None,
    on_tick: Callable[[World, TickContext, str, int], None] | None = None,
) -> Callable[[World, TickContext], None]:
    """Return a system that processes ability state each tick.

    Tick execution order:
    1. Process newly-invoked abilities (on_start; instantaneous get on_end too)
    2. Decrement active effects -- end expired ones (on_end)
    3. Tick still-active effects (on_tick)
    4. Decrement cooldowns
    5. Regenerate charges
    """
    # Track which abilities have had on_start fired.
    _started: set[str] = set()
    # Track manager restore generation to rebuild _started after restore.
    _seen_gen: list[int] = [manager._restore_gen]

    # Initialize _started from current manager state (handles case where
    # the system is created after a restore has already happened).
    for name in manager.defined_abilities():
        if name in manager._states:
            st = manager._states[name]
            if st.active_remaining > 0 or st.active_started_at != -1:
                _started.add(name)

    def ability_system(world: World, ctx: TickContext) -> None:
        # Detect restore: rebuild _started from manager state.
        if manager._restore_gen != _seen_gen[0]:
            _seen_gen[0] = manager._restore_gen
            _started.clear()
            for name in manager.defined_abilities():
                if name in manager._states:
                    st = manager._states[name]
                    if st.active_remaining > 0 or st.active_started_at != -1:
                        _started.add(name)

        # Snapshot of names for deterministic iteration
        names = list(manager._definition_order)

        # 1. Process newly-invoked abilities
        for name in names:
            if name not in manager._states:
                continue
            state = manager._states[name]

            if state.active_started_at != -1 and name not in _started:
                # Newly invoked ability detected
                defn = manager._definitions[name]

                if state.active_remaining == 0:
                    # Instantaneous ability (duration=0)
                    if on_start is not None:
                        on_start(world, ctx, name)
                    if on_end is not None:
                        on_end(world, ctx, name)
                    state.active_started_at = -1
                    state.cooldown_remaining = defn.cooldown
                else:
                    # Normal duration ability
                    if on_start is not None:
                        on_start(world, ctx, name)
                    _started.add(name)

        # 2. Decrement active effects, end expired
        for name in names:
            if name not in manager._states:
                continue
            state = manager._states[name]

            if state.active_remaining > 0:
                state.active_remaining -= 1
                if state.active_remaining == 0:
                    defn = manager._definitions[name]
                    if on_end is not None:
                        on_end(world, ctx, name)
                    state.active_started_at = -1
                    state.cooldown_remaining = defn.cooldown
                    _started.discard(name)

        # 3. Tick still-active effects
        if on_tick is not None:
            for name in names:
                if name not in manager._states:
                    continue
                state = manager._states[name]
                if state.active_remaining > 0:
                    on_tick(world, ctx, name, state.active_remaining)

        # 4. Decrement cooldowns
        for name in names:
            if name not in manager._states:
                continue
            state = manager._states[name]
            if state.cooldown_remaining > 0:
                state.cooldown_remaining -= 1

        # 5. Regenerate charges
        for name in names:
            if name not in manager._states:
                continue
            state = manager._states[name]
            defn = manager._definitions[name]

            if state.regen_remaining > 0:
                state.regen_remaining -= 1
                if state.regen_remaining == 0 and state.charges < defn.max_charges:
                    state.charges += 1
                    # If still below max, restart regen timer
                    if state.charges < defn.max_charges:
                        state.regen_remaining = defn.charge_regen

    return ability_system
