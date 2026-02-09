from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tick import Engine

from tick_spatial import Pos2D, Grid2D
from tick_schedule import Timer
from tick_fsm import FSM
from tick_colony.containment import Container, ContainedBy
from tick_colony.events import EventLog
from tick_event import EventScheduler
from tick_atlas import CellMap
from tick_ability import AbilityManager
from tick_resource import Inventory, ResourceRegistry
from tick_colony.lifecycle import Lifecycle
from tick_colony.needs import NeedSet
from tick_colony.stats import Modifiers, StatBlock

_COLONY_COMPONENTS = (Pos2D, Timer, FSM, NeedSet, StatBlock, Modifiers, Container, ContainedBy, Lifecycle, Inventory)


class ColonySnapshot:
    def __init__(self, grid: Grid2D | None = None,
                 event_log: EventLog | None = None,
                 scheduler: EventScheduler | None = None,
                 cellmap: CellMap | None = None,
                 ability_manager: AbilityManager | None = None,
                 resource_registry: ResourceRegistry | None = None) -> None:
        self._grid = grid
        self._event_log = event_log
        self._scheduler = scheduler
        self._cellmap = cellmap
        self._ability_manager = ability_manager
        self._resource_registry = resource_registry

    def snapshot(self, engine: Engine) -> dict[str, Any]:
        data = engine.snapshot()
        colony: dict[str, Any] = {}
        if self._grid is not None:
            colony["grid"] = {"width": self._grid.width, "height": self._grid.height}
        if self._event_log is not None:
            colony["events"] = self._event_log.snapshot()
        if self._scheduler is not None:
            colony["scheduler"] = self._scheduler.snapshot()
        if self._cellmap is not None:
            colony["cellmap"] = self._cellmap.snapshot()
        if self._ability_manager is not None:
            colony["ability_manager"] = self._ability_manager.snapshot()
        if self._resource_registry is not None:
            colony["resource_registry"] = self._resource_registry.snapshot()
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
        if self._scheduler is not None:
            self._scheduler.restore(colony.get("scheduler", {}))
        if self._cellmap is not None and "cellmap" in colony:
            self._cellmap.restore(colony["cellmap"])
        if self._ability_manager is not None and "ability_manager" in colony:
            self._ability_manager.restore(colony["ability_manager"])
        if self._resource_registry is not None and "resource_registry" in colony:
            self._resource_registry.restore(colony["resource_registry"])
