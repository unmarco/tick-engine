"""EventScheduler — standalone world-level event manager."""
from __future__ import annotations

import random as _random_mod
from typing import Any

from tick_event.types import ActiveEvent, CycleDef, CycleState, EventDef


class EventScheduler:
    """Manages event definitions, active events, cycles, and cooldowns."""

    def __init__(self) -> None:
        self._definitions: dict[str, EventDef] = {}
        self._definition_order: list[str] = []
        self._active: dict[str, ActiveEvent] = {}
        self._cooldowns: dict[str, int] = {}
        self._cycle_defs: dict[str, CycleDef] = {}
        self._cycle_states: dict[str, CycleState] = {}

    # --- Registration ---

    def define(self, event: EventDef) -> None:
        """Register an event definition. Insertion order preserved."""
        if event.name not in self._definitions:
            self._definition_order.append(event.name)
        self._definitions[event.name] = event

    def define_cycle(self, cycle: CycleDef) -> None:
        """Register a cycle definition and initialize its state."""
        self._cycle_defs[cycle.name] = cycle
        if cycle.delay > 0:
            self._cycle_states[cycle.name] = CycleState(
                name=cycle.name, phase_index=-1, delay_remaining=cycle.delay
            )
        else:
            self._cycle_states[cycle.name] = CycleState(
                name=cycle.name, phase_index=0, delay_remaining=0
            )

    # --- Queries ---

    def is_active(self, name: str) -> bool:
        """Check if an event or cycle phase is currently active."""
        if name in self._active:
            return True
        for cstate in self._cycle_states.values():
            if cstate.phase_index < 0:
                continue
            cdef = self._cycle_defs[cstate.name]
            phase_name, _ = cdef.phases[cstate.phase_index]
            if phase_name == name:
                return True
        return False

    def active_events(self) -> list[ActiveEvent]:
        """Return all currently active non-cycle events."""
        return list(self._active.values())

    def time_remaining(self, name: str) -> int:
        """Remaining ticks for an event or cycle phase. 0 if inactive."""
        if name in self._active:
            return self._active[name].remaining
        for cstate in self._cycle_states.values():
            if cstate.phase_index < 0:
                continue
            cdef = self._cycle_defs[cstate.name]
            phase_name, _ = cdef.phases[cstate.phase_index]
            if phase_name == name:
                return cstate.delay_remaining  # reused as phase remaining
        return 0

    def definition(self, name: str) -> EventDef | None:
        """Look up an event definition by name."""
        return self._definitions.get(name)

    # --- Internal (called by system) ---

    def _activate(self, name: str, duration: int, tick_number: int) -> None:
        """Start an event."""
        self._active[name] = ActiveEvent(
            name=name, remaining=duration, started_at=tick_number
        )

    def _deactivate(self, name: str) -> None:
        """End an event and start cooldown if defined."""
        del self._active[name]
        defn = self._definitions.get(name)
        if defn and defn.cooldown > 0:
            self._cooldowns[name] = defn.cooldown

    def _decrement_cooldowns(self) -> None:
        """Tick all cooldowns down by 1, removing expired ones."""
        expired = [k for k, v in self._cooldowns.items() if v <= 1]
        for k in expired:
            del self._cooldowns[k]
        for k in self._cooldowns:
            self._cooldowns[k] -= 1

    def _is_on_cooldown(self, name: str) -> bool:
        return name in self._cooldowns

    def _resolve_duration(
        self, defn: EventDef, rng: _random_mod.Random
    ) -> int:
        """Resolve fixed or random duration."""
        if isinstance(defn.duration, tuple):
            lo, hi = defn.duration
            return rng.randint(lo, hi)
        return defn.duration

    def _advance_cycle(
        self, cycle_name: str, tick_number: int
    ) -> tuple[str | None, str | None]:
        """Advance a cycle by one tick. Returns (ended_phase, started_phase)."""
        cstate = self._cycle_states[cycle_name]
        cdef = self._cycle_defs[cycle_name]

        if cstate.phase_index == -1:
            # In initial delay
            cstate.delay_remaining -= 1
            if cstate.delay_remaining <= 0:
                cstate.phase_index = 0
                _, dur = cdef.phases[0]
                cstate.delay_remaining = dur
                phase_name = cdef.phases[0][0]
                return None, phase_name
            return None, None

        # In a phase — decrement remaining
        cstate.delay_remaining -= 1
        if cstate.delay_remaining <= 0:
            old_phase = cdef.phases[cstate.phase_index][0]
            cstate.phase_index = (cstate.phase_index + 1) % len(cdef.phases)
            new_phase_name, new_dur = cdef.phases[cstate.phase_index]
            cstate.delay_remaining = new_dur
            return old_phase, new_phase_name

        return None, None

    # --- Serialization ---

    def snapshot(self) -> dict[str, Any]:
        """Serialize runtime state (not definitions)."""
        return {
            "active_events": [
                {
                    "name": ae.name,
                    "remaining": ae.remaining,
                    "started_at": ae.started_at,
                }
                for ae in self._active.values()
            ],
            "cooldowns": dict(self._cooldowns),
            "cycles": [
                {
                    "name": cs.name,
                    "phase_index": cs.phase_index,
                    "delay_remaining": cs.delay_remaining,
                }
                for cs in self._cycle_states.values()
            ],
        }

    def restore(self, data: dict[str, Any]) -> None:
        """Restore runtime state. Definitions must be re-registered first."""
        self._active.clear()
        for ae_data in data.get("active_events", []):
            ae = ActiveEvent(**ae_data)
            self._active[ae.name] = ae

        self._cooldowns = dict(data.get("cooldowns", {}))

        for cs_data in data.get("cycles", []):
            cs = CycleState(**cs_data)
            self._cycle_states[cs.name] = cs
