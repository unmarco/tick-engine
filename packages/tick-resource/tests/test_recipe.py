"""Tests for Recipe and crafting functions."""
from __future__ import annotations

import pytest
from tick_resource import Inventory, InventoryHelper, Recipe, can_craft, craft


class TestRecipeConstruction:
    def test_minimal(self) -> None:
        recipe = Recipe(name="craft_wood")
        assert recipe.name == "craft_wood"
        assert recipe.inputs == {}
        assert recipe.outputs == {}
        assert recipe.duration == 0

    def test_full(self) -> None:
        recipe = Recipe(
            name="craft_sword",
            inputs={"iron": 3, "wood": 1},
            outputs={"sword": 1},
            duration=10,
        )
        assert recipe.name == "craft_sword"
        assert recipe.inputs == {"iron": 3, "wood": 1}
        assert recipe.outputs == {"sword": 1}
        assert recipe.duration == 10

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name must be non-empty"):
            Recipe(name="")

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="duration must be >= 0"):
            Recipe(name="instant", duration=-1)


class TestRecipeImmutability:
    def test_frozen_attribute_modification_raises(self) -> None:
        recipe = Recipe(name="craft_axe")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            recipe.name = "craft_pickaxe"  # type: ignore[misc]


class TestCanCraft:
    def test_can_craft_sufficient(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5})
        recipe = Recipe(name="craft", inputs={"wood": 5, "stone": 3})
        assert can_craft(inv, recipe) is True

    def test_can_craft_exact(self) -> None:
        inv = Inventory(slots={"wood": 5, "stone": 3})
        recipe = Recipe(name="craft", inputs={"wood": 5, "stone": 3})
        assert can_craft(inv, recipe) is True

    def test_can_craft_insufficient(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 2})
        recipe = Recipe(name="craft", inputs={"wood": 5, "stone": 3})
        assert can_craft(inv, recipe) is False

    def test_can_craft_missing_resource(self) -> None:
        inv = Inventory(slots={"wood": 10})
        recipe = Recipe(name="craft", inputs={"wood": 5, "stone": 3})
        assert can_craft(inv, recipe) is False

    def test_can_craft_empty_inputs(self) -> None:
        inv = Inventory(slots={"wood": 10})
        recipe = Recipe(name="craft", inputs={})
        assert can_craft(inv, recipe) is True


class TestCraft:
    def test_craft_success_consumes_inputs_produces_outputs(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5})
        recipe = Recipe(
            name="craft_pickaxe",
            inputs={"wood": 2, "stone": 3},
            outputs={"pickaxe": 1},
        )
        result = craft(inv, recipe)
        assert result is True
        assert inv.slots["wood"] == 8
        assert inv.slots["stone"] == 2
        assert inv.slots["pickaxe"] == 1

    def test_craft_failure_unchanged(self) -> None:
        inv = Inventory(slots={"wood": 1, "stone": 5})
        recipe = Recipe(
            name="craft_pickaxe",
            inputs={"wood": 2, "stone": 3},
            outputs={"pickaxe": 1},
        )
        result = craft(inv, recipe)
        assert result is False
        assert inv.slots["wood"] == 1
        assert inv.slots["stone"] == 5
        assert "pickaxe" not in inv.slots

    def test_craft_multiple_outputs(self) -> None:
        inv = Inventory(slots={"log": 5})
        recipe = Recipe(
            name="split_log",
            inputs={"log": 1},
            outputs={"plank": 4, "sawdust": 1},
        )
        result = craft(inv, recipe)
        assert result is True
        assert inv.slots["log"] == 4
        assert inv.slots["plank"] == 4
        assert inv.slots["sawdust"] == 1

    def test_craft_accumulates_existing(self) -> None:
        inv = Inventory(slots={"wood": 10, "plank": 5})
        recipe = Recipe(name="craft", inputs={"wood": 5}, outputs={"plank": 3})
        result = craft(inv, recipe)
        assert result is True
        assert inv.slots["wood"] == 5
        assert inv.slots["plank"] == 8

    def test_craft_clears_empty_slot(self) -> None:
        inv = Inventory(slots={"wood": 5})
        recipe = Recipe(name="craft", inputs={"wood": 5}, outputs={"plank": 10})
        result = craft(inv, recipe)
        assert result is True
        assert "wood" not in inv.slots
        assert inv.slots["plank"] == 10
