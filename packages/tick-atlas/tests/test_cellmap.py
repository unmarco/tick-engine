"""Tests for CellMap CRUD, queries, and bulk operations."""
from __future__ import annotations

import pytest

from tick_atlas.cellmap import CellMap
from tick_atlas.types import CellDef

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=2.0, properties={"trees": True})
WATER = CellDef(name="water", passable=False, move_cost=5.0)
ROAD = CellDef(name="road", move_cost=0.5)
SAND = CellDef(name="sand", move_cost=1.5)


class TestCellMapConstruction:
    def test_default(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.default == GRASS

    def test_default_auto_registered(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.default.name == "grass"


class TestCellMapSetAndAt:
    def test_unset_returns_default(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.at((0, 0)) == GRASS

    def test_set_and_get(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((3, 5), FOREST)
        assert cm.at((3, 5)) == FOREST

    def test_set_to_default_removes(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FOREST)
        cm.set((1, 1), GRASS)
        assert (1, 1) not in cm.coords()

    def test_overwrite(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), FOREST)
        cm.set((0, 0), WATER)
        assert cm.at((0, 0)) == WATER

    def test_auto_registers(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), FOREST)
        # Should be able to snapshot/restore without explicit register
        snap = cm.snapshot()
        assert "forest" in snap["cells"].values()


class TestCellMapClear:
    def test_clear_resets_to_default(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((2, 3), FOREST)
        cm.clear((2, 3))
        assert cm.at((2, 3)) == GRASS

    def test_clear_unset_no_error(self) -> None:
        cm = CellMap(default=GRASS)
        cm.clear((99, 99))  # should not raise

    def test_clear_all(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), FOREST)
        cm.set((1, 1), WATER)
        cm.clear_all()
        assert cm.coords() == []
        assert cm.at((0, 0)) == GRASS


class TestCellMapPassable:
    def test_passable_default(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.passable((0, 0)) is True

    def test_passable_true(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FOREST)
        assert cm.passable((1, 1)) is True

    def test_passable_false(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((2, 2), WATER)
        assert cm.passable((2, 2)) is False


class TestCellMapMoveCost:
    def test_default_cost(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.move_cost((0, 0), (1, 0)) == 1.0

    def test_custom_cost(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((5, 5), FOREST)
        assert cm.move_cost((4, 5), (5, 5)) == 2.0

    def test_cost_uses_destination(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), ROAD)
        cm.set((1, 0), FOREST)
        # Cost should be destination's cost
        assert cm.move_cost((0, 0), (1, 0)) == 2.0
        assert cm.move_cost((1, 0), (0, 0)) == 0.5


class TestCellMapOfType:
    def test_of_type_empty(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.of_type("forest") == []

    def test_of_type_multiple(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FOREST)
        cm.set((2, 2), FOREST)
        cm.set((3, 3), WATER)
        result = cm.of_type("forest")
        assert sorted(result) == [(1, 1), (2, 2)]

    def test_of_type_excludes_default(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0), FOREST)
        # Default cells are not stored, so of_type("grass") returns []
        assert cm.of_type("grass") == []


class TestCellMapCoords:
    def test_empty(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.coords() == []

    def test_non_default_only(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FOREST)
        cm.set((2, 2), WATER)
        assert sorted(cm.coords()) == [(1, 1), (2, 2)]


class TestCellMapRegistration:
    def test_register_explicit(self) -> None:
        cm = CellMap(default=GRASS)
        cm.register(FOREST)
        # Should not raise on snapshot/restore with this name

    def test_register_collision_raises(self) -> None:
        cm = CellMap(default=GRASS)
        cm.register(CellDef(name="x", move_cost=1.0))
        with pytest.raises(ValueError, match="name collision"):
            cm.register(CellDef(name="x", move_cost=2.0))

    def test_register_same_def_ok(self) -> None:
        cm = CellMap(default=GRASS)
        cm.register(CellDef(name="x", move_cost=1.0))
        cm.register(CellDef(name="x", move_cost=1.0))  # same definition, no error


class TestCellMapFill:
    def test_fill(self) -> None:
        cm = CellMap(default=GRASS)
        coords = [(0, 0), (1, 0), (2, 0)]
        cm.fill(coords, ROAD)
        for c in coords:
            assert cm.at(c) == ROAD

    def test_fill_empty_list(self) -> None:
        cm = CellMap(default=GRASS)
        cm.fill([], ROAD)
        assert cm.coords() == []


class TestCellMapFillRect:
    def test_fill_rect(self) -> None:
        cm = CellMap(default=GRASS)
        cm.fill_rect((1, 1), (3, 3), WATER)
        for x in range(1, 4):
            for y in range(1, 4):
                assert cm.at((x, y)) == WATER

    def test_fill_rect_reversed_corners(self) -> None:
        cm = CellMap(default=GRASS)
        cm.fill_rect((3, 3), (1, 1), WATER)
        for x in range(1, 4):
            for y in range(1, 4):
                assert cm.at((x, y)) == WATER

    def test_fill_rect_single_cell(self) -> None:
        cm = CellMap(default=GRASS)
        cm.fill_rect((5, 5), (5, 5), FOREST)
        assert cm.at((5, 5)) == FOREST
        assert len(cm.coords()) == 1

    def test_fill_rect_outside_untouched(self) -> None:
        cm = CellMap(default=GRASS)
        cm.fill_rect((0, 0), (1, 1), WATER)
        assert cm.at((2, 2)) == GRASS


class TestCellMap3DCoords:
    def test_3d_set_and_get(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 2, 3), FOREST)
        assert cm.at((1, 2, 3)) == FOREST

    def test_3d_passable(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((0, 0, 0), WATER)
        assert cm.passable((0, 0, 0)) is False

    def test_3d_move_cost(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1, 1), SAND)
        assert cm.move_cost((0, 0, 0), (1, 1, 1)) == 1.5
