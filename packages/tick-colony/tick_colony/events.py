from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class Event:
    tick: int
    type: str
    data: dict[str, Any]


class EventLog:
    def __init__(self, max_entries: int = 0) -> None:
        self._max = max_entries
        maxlen = max_entries if max_entries > 0 else None
        self._events: deque[Event] = deque(maxlen=maxlen)

    def emit(self, tick: int, type: str, **data: Any) -> None:
        self._events.append(Event(tick=tick, type=type, data=data))

    def query(self, type: str | None = None, after: int | None = None,
              before: int | None = None) -> list[Event]:
        result: list[Event] = list(self._events)
        if type is not None:
            result = [e for e in result if e.type == type]
        if after is not None:
            result = [e for e in result if e.tick > after]
        if before is not None:
            result = [e for e in result if e.tick < before]
        return result

    def last(self, type: str) -> Event | None:
        for e in reversed(self._events):
            if e.type == type:
                return e
        return None

    def snapshot(self) -> list[dict]:
        return [{"tick": e.tick, "type": e.type, "data": e.data} for e in self._events]

    def restore(self, data: list[dict]) -> None:
        self._events.clear()
        for d in data:
            self._events.append(Event(tick=d["tick"], type=d["type"], data=d["data"]))

    def __len__(self) -> int:
        return len(self._events)
