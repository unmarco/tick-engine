"""Tests for ResourceRegistry."""
from __future__ import annotations

import pytest
from tick_resource import ResourceDef, ResourceRegistry


class TestRegistryBasics:
    def test_define_and_get(self) -> None:
        registry = ResourceRegistry()
        wood = ResourceDef(name="wood")
        registry.define(wood)
        retrieved = registry.get("wood")
        assert retrieved is wood

    def test_define_overwrites(self) -> None:
        registry = ResourceRegistry()
        wood1 = ResourceDef(name="wood", max_stack=10)
        wood2 = ResourceDef(name="wood", max_stack=99)
        registry.define(wood1)
        registry.define(wood2)
        retrieved = registry.get("wood")
        assert retrieved.max_stack == 99

    def test_get_nonexistent_raises(self) -> None:
        registry = ResourceRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_has_true(self) -> None:
        registry = ResourceRegistry()
        registry.define(ResourceDef(name="stone"))
        assert registry.has("stone") is True

    def test_has_false(self) -> None:
        registry = ResourceRegistry()
        assert registry.has("stone") is False

    def test_defined_resources_empty(self) -> None:
        registry = ResourceRegistry()
        assert registry.defined_resources() == []

    def test_defined_resources_multiple(self) -> None:
        registry = ResourceRegistry()
        registry.define(ResourceDef(name="wood"))
        registry.define(ResourceDef(name="stone"))
        registry.define(ResourceDef(name="gold"))
        resources = registry.defined_resources()
        assert set(resources) == {"wood", "stone", "gold"}

    def test_remove_existing(self) -> None:
        registry = ResourceRegistry()
        registry.define(ResourceDef(name="wood"))
        registry.remove("wood")
        assert registry.has("wood") is False

    def test_remove_nonexistent_raises(self) -> None:
        registry = ResourceRegistry()
        with pytest.raises(KeyError):
            registry.remove("nonexistent")


class TestRegistrySnapshot:
    def test_snapshot_empty(self) -> None:
        registry = ResourceRegistry()
        snapshot = registry.snapshot()
        assert snapshot == {"definitions": {}}

    def test_snapshot_with_properties(self) -> None:
        registry = ResourceRegistry()
        wood = ResourceDef(
            name="wood",
            max_stack=99,
            properties={"flammable": True},
            decay_rate=0,
        )
        registry.define(wood)
        snapshot = registry.snapshot()
        assert snapshot == {
            "definitions": {
                "wood": {
                    "name": "wood",
                    "max_stack": 99,
                    "properties": {"flammable": True},
                    "decay_rate": 0,
                }
            }
        }


class TestRegistryRestore:
    def test_restore_empty(self) -> None:
        registry = ResourceRegistry()
        registry.define(ResourceDef(name="wood"))
        registry.restore({"definitions": {}})
        assert registry.defined_resources() == []

    def test_restore_with_data(self) -> None:
        registry = ResourceRegistry()
        data = {
            "definitions": {
                "stone": {
                    "name": "stone",
                    "max_stack": 50,
                    "properties": {},
                    "decay_rate": 0,
                }
            }
        }
        registry.restore(data)
        stone = registry.get("stone")
        assert stone.name == "stone"
        assert stone.max_stack == 50

    def test_restore_with_properties(self) -> None:
        registry = ResourceRegistry()
        data = {
            "definitions": {
                "food": {
                    "name": "food",
                    "max_stack": 10,
                    "properties": {"edible": True, "calories": 100},
                    "decay_rate": 5,
                }
            }
        }
        registry.restore(data)
        food = registry.get("food")
        assert food.properties == {"edible": True, "calories": 100}
        assert food.decay_rate == 5

    def test_roundtrip_snapshot_restore(self) -> None:
        registry1 = ResourceRegistry()
        registry1.define(ResourceDef(name="wood", max_stack=99))
        registry1.define(
            ResourceDef(name="food", decay_rate=3, properties={"edible": True})
        )

        snapshot = registry1.snapshot()

        registry2 = ResourceRegistry()
        registry2.restore(snapshot)

        assert set(registry2.defined_resources()) == {"wood", "food"}
        wood = registry2.get("wood")
        food = registry2.get("food")
        assert wood.max_stack == 99
        assert food.decay_rate == 3
        assert food.properties == {"edible": True}
