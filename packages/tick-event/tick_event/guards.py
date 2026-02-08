"""EventGuards registry for world-level event conditions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick import World

    from tick_event.scheduler import EventScheduler


class EventGuards:
    """Maps guard name strings to callable predicates."""

    def __init__(self) -> None:
        self._guards: dict[str, Callable[[World, EventScheduler], bool]] = {}

    def register(
        self, name: str, fn: Callable[[World, EventScheduler], bool]
    ) -> None:
        """Register a named guard. Overwrites if already registered."""
        self._guards[name] = fn

    def check(self, name: str, world: World, scheduler: EventScheduler) -> bool:
        """Evaluate a guard. Raises KeyError if not registered."""
        return self._guards[name](world, scheduler)

    def has(self, name: str) -> bool:
        """Check if guard name is registered."""
        return name in self._guards

    def names(self) -> list[str]:
        """List all registered guard names."""
        return list(self._guards)
