"""ResourceRegistry class."""
from __future__ import annotations

import copy
from typing import Any

from tick_resource.types import ResourceDef


class ResourceRegistry:
    """Stores resource type definitions with snapshot/restore support."""

    def __init__(self) -> None:
        self._definitions: dict[str, ResourceDef] = {}

    def define(self, resource_def: ResourceDef) -> None:
        """Register a resource type. Overwrites if name exists."""
        self._definitions[resource_def.name] = resource_def

    def get(self, name: str) -> ResourceDef:
        """Look up definition. Raises KeyError if not defined."""
        if name not in self._definitions:
            raise KeyError(name)
        return self._definitions[name]

    def has(self, name: str) -> bool:
        """Check if resource name is defined."""
        return name in self._definitions

    def defined_resources(self) -> list[str]:
        """Return all defined resource names."""
        return list(self._definitions.keys())

    def remove(self, name: str) -> None:
        """Remove a resource definition. Raises KeyError if not defined."""
        if name not in self._definitions:
            raise KeyError(name)
        del self._definitions[name]

    def snapshot(self) -> dict[str, Any]:
        """Serialize registry state."""
        definitions: dict[str, dict[str, Any]] = {}
        for name, defn in self._definitions.items():
            definitions[name] = {
                "name": defn.name,
                "max_stack": defn.max_stack,
                "properties": copy.deepcopy(defn.properties),
                "decay_rate": defn.decay_rate,
            }
        return {"definitions": definitions}

    def restore(self, data: dict[str, Any]) -> None:
        """Restore registry state from snapshot data."""
        self._definitions.clear()
        for _name, defn_data in data.get("definitions", {}).items():
            self._definitions[defn_data["name"]] = ResourceDef(
                name=defn_data["name"],
                max_stack=defn_data["max_stack"],
                properties=copy.deepcopy(defn_data["properties"]),
                decay_rate=defn_data["decay_rate"],
            )
