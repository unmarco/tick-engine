"""Core data types for player-triggered abilities."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AbilityDef:
    """Definition of an ability. Not serialized."""

    name: str
    duration: int | tuple[int, int]  # fixed ticks or (min, max) random range
    cooldown: int = 0  # ticks after effect ends before re-use
    max_charges: int = 1  # -1 for unlimited
    charge_regen: int = 0  # ticks between charge regeneration (0 = no regen)
    conditions: list[str] = field(default_factory=list)  # guard names, ALL must pass


@dataclass
class AbilityState:
    """Runtime state of one ability. Mutable, serializable."""

    name: str
    charges: int
    cooldown_remaining: int = 0
    active_remaining: int = 0
    active_started_at: int = -1
    regen_remaining: int = 0
