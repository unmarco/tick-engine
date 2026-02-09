"""JSONL chronicle recorder — captures structured events for offline analysis."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tick_signal import SignalBus


# All signal types we record.
_SIGNAL_TYPES = (
    "birth", "death", "exhaustion", "season", "event_start", "event_end",
    "ability", "command", "food_deposited", "build_done", "census",
    "raid_damage",
)


class ChronicleRecorder:
    """Subscribes to a SignalBus and accumulates structured JSONL records."""

    def __init__(self, bus: SignalBus, clock_fn: Any) -> None:
        """*clock_fn* is a callable returning the current tick number."""
        self._records: list[dict[str, Any]] = []
        self._clock_fn = clock_fn
        for sig in _SIGNAL_TYPES:
            bus.subscribe(sig, self._make_handler(sig))

    def _make_handler(self, signal_type: str):
        def handler(signal: str, data: dict[str, Any]) -> None:
            record: dict[str, Any] = {
                "tick": self._clock_fn(),
                "type": signal_type,
            }
            record.update(data)
            self._records.append(record)
        return handler

    @property
    def count(self) -> int:
        return len(self._records)

    def write(self, path: str | Path) -> int:
        """Write all records as JSONL. Returns number of lines written."""
        p = Path(path)
        with p.open("w") as f:
            for record in self._records:
                f.write(json.dumps(record, default=str) + "\n")
        return len(self._records)
