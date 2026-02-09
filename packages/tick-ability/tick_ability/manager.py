"""AbilityManager — standalone ability manager."""
from __future__ import annotations

import random as _random_mod
from typing import TYPE_CHECKING, Any

from tick_ability.types import AbilityDef, AbilityState

if TYPE_CHECKING:
    from tick import TickContext, World

    from tick_ability.guards import AbilityGuards


class AbilityManager:
    """Manages ability definitions, runtime states, and invocation."""

    def __init__(self) -> None:
        self._definitions: dict[str, AbilityDef] = {}
        self._definition_order: list[str] = []
        self._states: dict[str, AbilityState] = {}
        self._restore_gen: int = 0

    # --- Registration ---

    def define(self, ability: AbilityDef) -> None:
        """Register an ability definition. Insertion order preserved.

        Initializes runtime state with charges set to max_charges
        (or 0 if max_charges is -1, since unlimited means charges
        are not tracked). Re-defining preserves existing state.
        """
        if ability.name not in self._definitions:
            self._definition_order.append(ability.name)
            initial_charges = 0 if ability.max_charges == -1 else ability.max_charges
            self._states[ability.name] = AbilityState(
                name=ability.name, charges=initial_charges
            )
        self._definitions[ability.name] = ability

    def definition(self, name: str) -> AbilityDef | None:
        """Look up an ability definition by name."""
        return self._definitions.get(name)

    # --- Invocation ---

    def invoke(
        self,
        name: str,
        world: World,
        ctx: TickContext,
        guards: AbilityGuards | None = None,
    ) -> bool:
        """Attempt to invoke an ability. Returns True if successful."""
        # 1. Not defined
        if name not in self._definitions:
            return False

        defn = self._definitions[name]
        state = self._states[name]

        # 2. Already active (includes pending instantaneous abilities)
        if state.active_remaining > 0 or state.active_started_at != -1:
            return False

        # 3. On cooldown
        if self._is_on_cooldown(name):
            return False

        # 4. No charges (skip for unlimited)
        if defn.max_charges != -1 and state.charges == 0:
            return False

        # 5. Guard failure
        if guards is not None:
            for guard_name in defn.conditions:
                if not guards.check(guard_name, world, self):
                    return False

        # All checks passed — invoke
        # Consume charge (if not unlimited)
        if defn.max_charges != -1:
            state.charges -= 1

        # Resolve duration
        duration = self._resolve_duration(defn, ctx.random)
        state.active_remaining = duration
        state.active_started_at = ctx.tick_number

        # Start regen if needed
        if (
            defn.max_charges != -1
            and defn.charge_regen > 0
            and state.charges < defn.max_charges
            and state.regen_remaining == 0
        ):
            state.regen_remaining = defn.charge_regen

        return True

    # --- Queries ---

    def is_available(
        self,
        name: str,
        world: World,
        guards: AbilityGuards | None = None,
    ) -> bool:
        """Can this ability be invoked right now? Purely informational."""
        if name not in self._definitions:
            return False

        defn = self._definitions[name]
        state = self._states[name]

        # Not active (check both indicators)
        if state.active_remaining > 0 or state.active_started_at != -1:
            return False

        # Not on cooldown
        if self._is_on_cooldown(name):
            return False

        # Has charges (if tracked)
        if defn.max_charges != -1 and state.charges == 0:
            return False

        # All guards pass
        if guards is not None:
            for guard_name in defn.conditions:
                if not guards.check(guard_name, world, self):
                    return False

        return True

    def is_active(self, name: str) -> bool:
        """Is this ability's effect currently running?"""
        if name not in self._states:
            return False
        return self._states[name].active_remaining > 0

    def charges(self, name: str) -> int:
        """Current charge count. Returns -1 for unlimited. Raises KeyError."""
        if name not in self._definitions:
            raise KeyError(name)
        defn = self._definitions[name]
        if defn.max_charges == -1:
            return -1
        return self._states[name].charges

    def time_remaining(self, name: str) -> int:
        """Remaining ticks on active effect. 0 if not active. Raises KeyError."""
        if name not in self._states:
            raise KeyError(name)
        return self._states[name].active_remaining

    def cooldown_remaining(self, name: str) -> int:
        """Remaining ticks on cooldown. 0 if not on cooldown. Raises KeyError."""
        if name not in self._states:
            raise KeyError(name)
        return self._states[name].cooldown_remaining

    def state(self, name: str) -> AbilityState | None:
        """Direct access to runtime state. Returns None if not defined."""
        return self._states.get(name)

    def defined_abilities(self) -> list[str]:
        """List all defined ability names in definition order."""
        return list(self._definition_order)

    # --- Internal helpers ---

    def _is_on_cooldown(self, name: str) -> bool:
        """Check if an ability is on cooldown."""
        return self._states[name].cooldown_remaining > 0

    def _resolve_duration(
        self, defn: AbilityDef, rng: _random_mod.Random
    ) -> int:
        """Resolve fixed or random duration."""
        if isinstance(defn.duration, tuple):
            lo, hi = defn.duration
            return rng.randint(lo, hi)
        return defn.duration

    # --- Serialization ---

    def snapshot(self) -> dict[str, Any]:
        """Serialize runtime state (not definitions)."""
        return {
            "abilities": [
                {
                    "name": s.name,
                    "charges": s.charges,
                    "cooldown_remaining": s.cooldown_remaining,
                    "active_remaining": s.active_remaining,
                    "active_started_at": s.active_started_at,
                    "regen_remaining": s.regen_remaining,
                }
                for s in self._states.values()
            ],
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore runtime state. Definitions must be re-registered first."""
        self._states.clear()
        for ab_data in data.get("abilities", []):
            name = ab_data["name"]
            if name not in self._definitions:
                continue  # skip unknown ability names
            self._states[name] = AbilityState(**ab_data)
        self._restore_gen += 1
