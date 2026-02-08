"""CellMap — sparse, dimension-agnostic cell property storage."""
from __future__ import annotations

from typing import Any

from tick_spatial.types import Coord

from tick_atlas.types import CellDef


class CellMap:
    """Maps coordinates to CellDef definitions.

    Sparse storage: only non-default cells are stored. Unset coordinates
    return the default CellDef.
    """

    def __init__(self, default: CellDef) -> None:
        self._default = default
        self._cells: dict[Coord, CellDef] = {}
        self._registry: dict[str, CellDef] = {}
        self.register(default)

    # --- Properties ---

    @property
    def default(self) -> CellDef:
        """The default cell type for unset coordinates."""
        return self._default

    # --- Registration ---

    def register(self, cell_def: CellDef) -> None:
        """Register a CellDef by name for snapshot/restore.

        Raises ValueError if a different CellDef with the same name exists.
        """
        existing = self._registry.get(cell_def.name)
        if existing is not None and existing != cell_def:
            raise ValueError(
                f"CellDef name collision: '{cell_def.name}' already registered "
                f"with different definition"
            )
        self._registry[cell_def.name] = cell_def

    # --- Mutation ---

    def set(self, coord: Coord, cell_def: CellDef) -> None:
        """Set the cell type at a coordinate.

        Auto-registers the CellDef. If set to the default, removes from storage.
        """
        self.register(cell_def)
        if cell_def == self._default:
            self._cells.pop(coord, None)
        else:
            self._cells[coord] = cell_def

    def clear(self, coord: Coord) -> None:
        """Reset a coordinate to the default cell type."""
        self._cells.pop(coord, None)

    def clear_all(self) -> None:
        """Reset all coordinates to the default cell type."""
        self._cells.clear()

    # --- Single-cell Queries ---

    def at(self, coord: Coord) -> CellDef:
        """Get the CellDef at a coordinate. Returns default for unset coords."""
        return self._cells.get(coord, self._default)

    def passable(self, coord: Coord) -> bool:
        """Check if a coordinate is passable. Matches pathfind(walkable=...) signature."""
        return self.at(coord).passable

    def move_cost(self, from_coord: Coord, to_coord: Coord) -> float:
        """Get movement cost to a coordinate. Matches pathfind(cost=...) signature."""
        return self.at(to_coord).move_cost

    # --- Multi-cell Queries ---

    def of_type(self, name: str) -> list[Coord]:
        """Return all non-default coordinates with the given cell type name."""
        return [c for c, d in self._cells.items() if d.name == name]

    def coords(self) -> list[Coord]:
        """Return all non-default coordinates."""
        return list(self._cells.keys())

    # --- Bulk Operations ---

    def fill(self, coords: list[Coord], cell_def: CellDef) -> None:
        """Set a list of coordinates to the same cell type."""
        for coord in coords:
            self.set(coord, cell_def)

    def fill_rect(
        self,
        corner1: tuple[int, int],
        corner2: tuple[int, int],
        cell_def: CellDef,
    ) -> None:
        """Fill a 2D rectangle (inclusive) with a cell type."""
        x1, y1 = min(corner1[0], corner2[0]), min(corner1[1], corner2[1])
        x2, y2 = max(corner1[0], corner2[0]), max(corner1[1], corner2[1])
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                self.set((x, y), cell_def)

    # --- Snapshot / Restore ---

    def snapshot(self) -> dict[str, Any]:
        """Serialize cell map state.

        Returns a dict with 'default' (name) and 'cells' (coord_str -> name).
        Only non-default cells are included.
        """
        cells: dict[str, str] = {}
        for coord, cell_def in self._cells.items():
            key = ",".join(str(c) for c in coord)
            cells[key] = cell_def.name
        return {"default": self._default.name, "cells": cells}

    def restore(self, data: dict[str, Any]) -> None:
        """Restore cell map state from snapshot data.

        All CellDefs must be registered first. Raises KeyError for unknown names.
        """
        self._cells.clear()
        default_name = data["default"]
        if default_name not in self._registry:
            raise KeyError(f"Unknown CellDef name: '{default_name}'")
        self._default = self._registry[default_name]

        for coord_str, name in data.get("cells", {}).items():
            if name not in self._registry:
                raise KeyError(f"Unknown CellDef name: '{name}'")
            coord: Coord = tuple(int(c) for c in coord_str.split(","))
            self._cells[coord] = self._registry[name]
