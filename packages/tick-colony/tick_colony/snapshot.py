from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tick import Engine

from tick_colony.actions import Action
from tick_colony.containment import Container, ContainedBy
from tick_colony.events import EventLog
from tick_colony.grid import Grid, Position
from tick_colony.lifecycle import Lifecycle
from tick_colony.needs import NeedSet
from tick_colony.stats import Modifiers, StatBlock

_COLONY_COMPONENTS = (Position, Action, NeedSet, StatBlock, Modifiers, Container, ContainedBy, Lifecycle)


class ColonySnapshot:
    def __init__(self, grid: Grid | None = None,
                 event_log: EventLog | None = None) -> None:
        self._grid = grid
        self._event_log = event_log

    def snapshot(self, engine: Engine) -> dict[str, Any]:
        data = engine.snapshot()
        colony: dict[str, Any] = {}
        if self._grid is not None:
            colony["grid"] = {"width": self._grid.width, "height": self._grid.height}
        if self._event_log is not None:
            colony["events"] = self._event_log.snapshot()
        data["colony"] = colony
        return data

    def restore(self, engine: Engine, data: dict[str, Any]) -> None:
        for ctype in _COLONY_COMPONENTS:
            engine.world.register_component(ctype)
        engine.restore(data)
        colony = data.get("colony", {})
        if self._grid is not None:
            self._grid.rebuild(engine.world)
        if self._event_log is not None:
            self._event_log.restore(colony.get("events", []))
