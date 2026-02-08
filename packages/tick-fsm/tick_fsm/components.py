"""FSM component."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FSM:
    """Finite state machine. Transition table maps states to guard/target pairs."""

    state: str
    transitions: dict[str, list[list[str]]]
