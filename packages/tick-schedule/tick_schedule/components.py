"""Timer and Periodic components."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Timer:
    """One-shot countdown. Fires when remaining reaches 0, then auto-detaches."""

    name: str
    remaining: int


@dataclass
class Periodic:
    """Recurring timer. Fires every `interval` ticks, never auto-detaches."""

    name: str
    interval: int
    elapsed: int = 0
