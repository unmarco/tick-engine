"""Tests for CellMap.matches()."""
from __future__ import annotations

from tick_atlas.cellmap import CellMap
from tick_atlas.types import CellDef

GRASS = CellDef(name="grass")
FOREST = CellDef(name="forest", move_cost=2.0, properties={"trees": True})
FARMLAND = CellDef(
    name="farmland",
    properties={"buildable": True, "fertile": True},
)
WATER = CellDef(name="water", passable=False, move_cost=5.0)


class TestMatchesBasic:
    def test_matches_single_property(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"buildable": True}) is True

    def test_matches_multiple_properties(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"buildable": True, "fertile": True}) is True

    def test_matches_terrain_key(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"terrain": "farmland"}) is True

    def test_matches_terrain_and_property(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"terrain": "farmland", "buildable": True}) is True

    def test_matches_empty_requirements(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {}) is True


class TestMatchesFalse:
    def test_default_cell_returns_false(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.matches((0, 0), {"buildable": True}) is False

    def test_unset_coord_returns_false(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((99, 99), {"buildable": True}) is False

    def test_wrong_property_value(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"buildable": False}) is False

    def test_missing_property(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"nonexistent": True}) is False

    def test_wrong_terrain(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"terrain": "forest"}) is False

    def test_partial_match_fails(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 1), FARMLAND)
        assert cm.matches((1, 1), {"buildable": True, "nonexistent": True}) is False


class TestMatches3D:
    def test_3d_coord(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((1, 2, 3), FARMLAND)
        assert cm.matches((1, 2, 3), {"buildable": True}) is True

    def test_3d_default_returns_false(self) -> None:
        cm = CellMap(default=GRASS)
        assert cm.matches((1, 2, 3), {"buildable": True}) is False


class TestMatchesWithForest:
    def test_forest_has_trees(self) -> None:
        cm = CellMap(default=GRASS)
        cm.set((5, 5), FOREST)
        assert cm.matches((5, 5), {"trees": True}) is True
        assert cm.matches((5, 5), {"terrain": "forest", "trees": True}) is True
