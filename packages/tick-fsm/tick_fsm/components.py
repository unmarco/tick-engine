"""FSM component."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FSM:
    """Finite state machine. Transition table maps states to guard/target pairs.

    Supports hierarchical states via dot-notation (e.g. ``"combat.attack"``).
    Parent-state transitions act as fallbacks for child states.

    ``initial`` maps parent states to their default child on entry.
    ``history`` tracks the last active child for each parent (auto-managed).
    """

    state: str
    transitions: dict[str, list[list[str]]]
    initial: dict[str, str] = field(default_factory=dict)
    history: dict[str, str] = field(default_factory=dict)
