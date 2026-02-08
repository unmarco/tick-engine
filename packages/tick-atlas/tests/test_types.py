"""Tests for CellDef dataclass."""
from __future__ import annotations

import pytest

from tick_atlas.types import CellDef


class TestCellDefConstruction:
    def test_minimal(self) -> None:
        c = CellDef(name="grass")
        assert c.name == "grass"
        assert c.passable is True
        assert c.move_cost == 1.0
        assert c.properties == {}

    def test_all_fields(self) -> None:
        c = CellDef(name="swamp", passable=True, move_cost=3.0, properties={"depth": 2})
        assert c.name == "swamp"
        assert c.passable is True
        assert c.move_cost == 3.0
        assert c.properties == {"depth": 2}

    def test_impassable(self) -> None:
        c = CellDef(name="wall", passable=False)
        assert c.passable is False

    def test_zero_move_cost(self) -> None:
        c = CellDef(name="road", move_cost=0.0)
        assert c.move_cost == 0.0


class TestCellDefValidation:
    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            CellDef(name="")

    def test_negative_move_cost_raises(self) -> None:
        with pytest.raises(ValueError, match="move_cost must be >= 0"):
            CellDef(name="bad", move_cost=-1.0)

    def test_negative_move_cost_message(self) -> None:
        with pytest.raises(ValueError, match="-0.5"):
            CellDef(name="bad", move_cost=-0.5)


class TestCellDefImmutability:
    def test_frozen_name(self) -> None:
        c = CellDef(name="stone")
        with pytest.raises(AttributeError):
            c.name = "other"  # type: ignore[misc]

    def test_frozen_passable(self) -> None:
        c = CellDef(name="stone")
        with pytest.raises(AttributeError):
            c.passable = False  # type: ignore[misc]

    def test_frozen_move_cost(self) -> None:
        c = CellDef(name="stone")
        with pytest.raises(AttributeError):
            c.move_cost = 5.0  # type: ignore[misc]

    def test_properties_dict_mutable(self) -> None:
        c = CellDef(name="tile", properties={"color": "red"})
        c.properties["color"] = "blue"
        assert c.properties["color"] == "blue"


class TestCellDefEquality:
    def test_equal(self) -> None:
        a = CellDef(name="grass")
        b = CellDef(name="grass")
        assert a == b

    def test_not_equal_name(self) -> None:
        assert CellDef(name="grass") != CellDef(name="dirt")

    def test_not_equal_passable(self) -> None:
        assert CellDef(name="x", passable=True) != CellDef(name="x", passable=False)

    def test_not_equal_cost(self) -> None:
        assert CellDef(name="x", move_cost=1.0) != CellDef(name="x", move_cost=2.0)
