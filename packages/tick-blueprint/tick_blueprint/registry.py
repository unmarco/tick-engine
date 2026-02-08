"""BlueprintRegistry class."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tick import EntityId, World


class BlueprintRegistry:
    """Stores and instantiates entity templates. Recipes are pure JSON-serializable dicts."""

    def __init__(self) -> None:
        self._recipes: dict[str, dict[str, dict[str, Any]]] = {}

    def define(self, name: str, recipe: dict[str, dict[str, Any]]) -> None:
        """Define a named template. Overwrites if name exists."""
        self._recipes[name] = recipe

    def spawn(
        self,
        world: World,
        name: str,
        overrides: dict[str, dict[str, Any]] | None = None,
    ) -> EntityId:
        """Create entity from template. Raises KeyError if name not defined."""
        if name not in self._recipes:
            raise KeyError(name)
        merged = copy.deepcopy(self._recipes[name])
        if overrides:
            for comp_name, fields in overrides.items():
                if comp_name in merged:
                    merged[comp_name].update(fields)
                else:
                    merged[comp_name] = dict(fields)
        eid = world.spawn()
        for comp_name, field_dict in merged.items():
            ctype = world._registry[comp_name]
            world.attach(eid, ctype(**field_dict))
        return eid

    def recipes(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return a copy of all defined recipes."""
        return copy.deepcopy(self._recipes)

    def has(self, name: str) -> bool:
        """Check if recipe name is defined."""
        return name in self._recipes

    def remove(self, name: str) -> None:
        """Remove a recipe. Raises KeyError if not defined."""
        if name not in self._recipes:
            raise KeyError(name)
        del self._recipes[name]
