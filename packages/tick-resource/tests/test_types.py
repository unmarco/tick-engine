"""Tests for ResourceDef."""
from __future__ import annotations

import pytest
from tick_resource import ResourceDef


class TestResourceDefConstruction:
    def test_minimal(self) -> None:
        rd = ResourceDef(name="wood")
        assert rd.name == "wood"
        assert rd.max_stack == -1
        assert rd.properties == {}
        assert rd.decay_rate == 0

    def test_with_max_stack(self) -> None:
        rd = ResourceDef(name="stone", max_stack=99)
        assert rd.name == "stone"
        assert rd.max_stack == 99

    def test_with_properties(self) -> None:
        rd = ResourceDef(name="food", properties={"edible": True, "calories": 50})
        assert rd.name == "food"
        assert rd.properties == {"edible": True, "calories": 50}

    def test_with_decay_rate(self) -> None:
        rd = ResourceDef(name="meat", decay_rate=5)
        assert rd.name == "meat"
        assert rd.decay_rate == 5

    def test_unlimited_stack(self) -> None:
        rd = ResourceDef(name="gold", max_stack=-1)
        assert rd.max_stack == -1


class TestResourceDefValidation:
    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name must be non-empty"):
            ResourceDef(name="")

    def test_max_stack_too_low_raises(self) -> None:
        with pytest.raises(ValueError, match="max_stack must be >= -1"):
            ResourceDef(name="ore", max_stack=-2)

    def test_negative_decay_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="decay_rate must be >= 0"):
            ResourceDef(name="metal", decay_rate=-1)


class TestResourceDefImmutability:
    def test_frozen_attribute_modification_raises(self) -> None:
        rd = ResourceDef(name="iron")
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            rd.name = "steel"  # type: ignore[misc]
