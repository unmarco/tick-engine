"""In-memory pub/sub event bus with per-tick flush semantics."""
from __future__ import annotations

from typing import Any, Callable

_Handler = Callable[[str, dict[str, Any]], None]


class SignalBus:

    def __init__(self) -> None:
        self._subscribers: dict[str, list[_Handler]] = {}
        self._queue: list[tuple[str, dict[str, Any]]] = []

    def subscribe(self, signal_name: str, handler: _Handler) -> None:
        self._subscribers.setdefault(signal_name, []).append(handler)

    def unsubscribe(self, signal_name: str, handler: _Handler) -> None:
        handlers = self._subscribers.get(signal_name)
        if handlers is None:
            return
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def publish(self, signal_name: str, **data: Any) -> None:
        self._queue.append((signal_name, data))

    def flush(self) -> None:
        snapshot = self._queue
        self._queue = []
        for signal_name, data in snapshot:
            for handler in self._subscribers.get(signal_name, []):
                handler(signal_name, data)

    def clear(self) -> None:
        self._queue.clear()
