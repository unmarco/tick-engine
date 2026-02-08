"""Shared type aliases and protocols for the tick engine."""

from __future__ import annotations

import random as _random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

EntityId = int


@dataclass(frozen=True, slots=True)
class TickContext:
    tick_number: int
    dt: float
    elapsed: float
    request_stop: Callable[[], None]
    random: _random.Random


class DeadEntityError(KeyError):
    """Raised when operating on an entity that is not alive."""

    def __init__(self, entity_id: int, message: str) -> None:
        self.entity_id = entity_id
        super().__init__(message)


class SnapshotError(Exception):
    """Raised on restore failures (version mismatch, unregistered component type)."""


if TYPE_CHECKING:
    from tick.world import World

System = Callable[["World", TickContext], None]
