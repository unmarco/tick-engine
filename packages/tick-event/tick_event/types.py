"""Core data types for world-level event scheduling."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EventDef:
    """Definition of a world-level event. Not serialized."""

    name: str
    duration: int | tuple[int, int]  # fixed ticks or (min, max) random range
    cooldown: int = 0  # min ticks before re-fire
    probability: float = 1.0  # per-evaluation chance [0.0, 1.0]
    conditions: list[str] = field(default_factory=list)  # guard names, ALL must pass


@dataclass
class ActiveEvent:
    """Runtime state of a currently-running event. Serializable."""

    name: str
    remaining: int
    started_at: int


@dataclass
class CycleDef:
    """Definition of a repeating phase cycle (e.g., seasons). Not serialized."""

    name: str
    phases: list[tuple[str, int]]  # (phase_name, duration_ticks)
    delay: int = 0  # ticks before first phase


@dataclass
class CycleState:
    """Runtime state of a cycle. Serializable."""

    name: str
    phase_index: int  # index into CycleDef.phases, -1 if in delay
    delay_remaining: int
