"""Tests for CellMap snapshot/restore."""
from __future__ import annotations

import pytest

from tick_atlas.cellmap import CellMap
from tick_atlas.types import CellDef

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=2.0)
WATER = CellDef(name="water", passable=False)
SAND = CellDef(name="sand", move_cost=1.5)


class TestSnapshot:
    def test_empty_snapshot(self) -> None:
        cm = CellMap(default=GRASS)
        snap = cm.snapshot()
        assert snap == {"default": "grass", "cells": {}}

    def test_snapshot_records_default(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.snapshot()["default"] == "grass"

    def test_snapshot_records_cells(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((3, 5), FOREST)
        snap = cm.snapshot()
        assert snap["cells"] == {"3,5": "forest"}

    def test_snapshot_multiple_cells(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 2), FOREST)
        cm.set((10, 10), WATER)
        snap = cm.snapshot()
        assert snap["cells"]["1,2"] == "forest"
        assert snap["cells"]["10,10"] == "water"

    def test_snapshot_excludes_default_cells(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), FOREST)
        cm.set((1, 1), GRASS)  # default, should not appear
        snap = cm.snapshot()
        assert "1,1" not in snap["cells"]


class TestRestore:
    def test_round_trip(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((3, 5), FOREST)
        cm.set((10, 10), WATER)
        snap = cm.snapshot()

        cm2 = CellMap(default=GRASS)
        cm2.register(FOREST)
        cm2.register(WATER)
        cm2.restore(snap)
        assert cm2.at((3, 5)) == FOREST
        assert cm2.at((10, 10)) == WATER
        assert cm2.at((0, 0)) == GRASS

    def test_restore_clears_existing(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), FOREST)
        cm.restore({"default": "grass", "cells": {}})
        assert cm.at((0, 0)) == GRASS
        assert cm.coords() == []

    def test_restore_unknown_cell_name_raises(self) -> None:
        cm = CellMap(default=GRASS)
        with pytest.raises(KeyError, match="unknown_type"):
            cm.restore({"default": "grass", "cells": {"0,0": "unknown_type"}})

    def test_restore_unknown_default_raises(self) -> None:
        cm = CellMap(default=GRASS)
        with pytest.raises(KeyError, match="missing"):
            cm.restore({"default": "missing", "cells": {}})

    def test_restore_preserves_registry(self) -> None:
        cm = CellMap(default=GRASS)
        cm.register(FOREST)
        cm.register(WATER)
        cm.restore({"default": "grass", "cells": {"5,5": "forest"}})
        # WATER should still be registered
        cm.restore({"default": "grass", "cells": {"5,5": "water"}})
        assert cm.at((5, 5)) == WATER


class TestSnapshotCoordSerialization:
    def test_2d_coord(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((3, 5), FOREST)
        snap = cm.snapshot()
        assert "3,5" in snap["cells"]

    def test_3d_coord(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 2, 3), FOREST)
        snap = cm.snapshot()
        assert "1,2,3" in snap["cells"]

    def test_3d_round_trip(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 2, 3), FOREST)
        snap = cm.snapshot()

        cm2 = CellMap(default=GRASS)
        cm2.register(FOREST)
        cm2.restore(snap)
        assert cm2.at((1, 2, 3)) == FOREST

    def test_negative_coords(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((-1, -2), FOREST)
        snap = cm.snapshot()
        assert "-1,-2" in snap["cells"]

        cm2 = CellMap(default=GRASS)
        cm2.register(FOREST)
        cm2.restore(snap)
        assert cm2.at((-1, -2)) == FOREST
