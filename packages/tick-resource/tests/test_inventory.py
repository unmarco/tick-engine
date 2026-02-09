"""Tests for Inventory and InventoryHelper."""
from __future__ import annotations

import pytest
from tick import Engine
from tick_resource import Inventory, InventoryHelper


class TestInventoryConstruction:
    def test_empty(self) -> None:
        inv = Inventory()
        assert inv.slots == {}
        assert inv.capacity == -1

    def test_with_capacity(self) -> None:
        inv = Inventory(capacity=100)
        assert inv.capacity == 100
        assert inv.slots == {}


class TestInventoryHelperAdd:
    def test_add_to_empty_slot(self) -> None:
        inv = Inventory()
        added = InventoryHelper.add(inv, "wood", 10)
        assert added == 10
        assert inv.slots["wood"] == 10

    def test_add_to_existing_slot(self) -> None:
        inv = Inventory(slots={"wood": 5})
        added = InventoryHelper.add(inv, "wood", 7)
        assert added == 7
        assert inv.slots["wood"] == 12

    def test_add_capacity_limited(self) -> None:
        inv = Inventory(slots={"wood": 20}, capacity=30)
        added = InventoryHelper.add(inv, "stone", 15)
        assert added == 10
        assert inv.slots["stone"] == 10

    def test_add_unlimited_capacity(self) -> None:
        inv = Inventory(capacity=-1)
        added = InventoryHelper.add(inv, "gold", 1000)
        assert added == 1000
        assert inv.slots["gold"] == 1000

    def test_add_zero(self) -> None:
        inv = Inventory()
        added = InventoryHelper.add(inv, "wood", 0)
        assert added == 0
        assert "wood" not in inv.slots

    def test_add_negative_raises(self) -> None:
        inv = Inventory()
        with pytest.raises(ValueError, match="amount must be >= 0"):
            InventoryHelper.add(inv, "wood", -5)


class TestInventoryHelperRemove:
    def test_remove_partial(self) -> None:
        inv = Inventory(slots={"wood": 10})
        removed = InventoryHelper.remove(inv, "wood", 3)
        assert removed == 3
        assert inv.slots["wood"] == 7

    def test_remove_all_clears_slot(self) -> None:
        inv = Inventory(slots={"wood": 10})
        removed = InventoryHelper.remove(inv, "wood", 10)
        assert removed == 10
        assert "wood" not in inv.slots

    def test_remove_more_than_available(self) -> None:
        inv = Inventory(slots={"wood": 5})
        removed = InventoryHelper.remove(inv, "wood", 10)
        assert removed == 5
        assert "wood" not in inv.slots

    def test_remove_nonexistent(self) -> None:
        inv = Inventory()
        removed = InventoryHelper.remove(inv, "wood", 5)
        assert removed == 0
        assert "wood" not in inv.slots

    def test_remove_zero(self) -> None:
        inv = Inventory(slots={"wood": 10})
        removed = InventoryHelper.remove(inv, "wood", 0)
        assert removed == 0
        assert inv.slots["wood"] == 10

    def test_remove_negative_raises(self) -> None:
        inv = Inventory(slots={"wood": 10})
        with pytest.raises(ValueError, match="amount must be >= 0"):
            InventoryHelper.remove(inv, "wood", -5)


class TestInventoryHelperCount:
    def test_count_existing(self) -> None:
        inv = Inventory(slots={"wood": 15})
        count = InventoryHelper.count(inv, "wood")
        assert count == 15

    def test_count_nonexistent(self) -> None:
        inv = Inventory()
        count = InventoryHelper.count(inv, "wood")
        assert count == 0


class TestInventoryHelperTotal:
    def test_total_empty(self) -> None:
        inv = Inventory()
        total = InventoryHelper.total(inv)
        assert total == 0

    def test_total_multiple_resources(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5, "gold": 3})
        total = InventoryHelper.total(inv)
        assert total == 18


class TestInventoryHelperHas:
    def test_has_sufficient(self) -> None:
        inv = Inventory(slots={"wood": 10})
        assert InventoryHelper.has(inv, "wood", 5) is True

    def test_has_exact(self) -> None:
        inv = Inventory(slots={"wood": 10})
        assert InventoryHelper.has(inv, "wood", 10) is True

    def test_has_insufficient(self) -> None:
        inv = Inventory(slots={"wood": 10})
        assert InventoryHelper.has(inv, "wood", 15) is False

    def test_has_nonexistent(self) -> None:
        inv = Inventory()
        assert InventoryHelper.has(inv, "wood", 1) is False

    def test_has_zero(self) -> None:
        inv = Inventory(slots={"wood": 10})
        assert InventoryHelper.has(inv, "wood", 0) is True

    def test_has_negative_raises(self) -> None:
        inv = Inventory(slots={"wood": 10})
        with pytest.raises(ValueError, match="amount must be >= 0"):
            InventoryHelper.has(inv, "wood", -1)


class TestInventoryHelperHasAll:
    def test_has_all_met(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5})
        assert InventoryHelper.has_all(inv, {"wood": 5, "stone": 3}) is True

    def test_has_all_exact(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5})
        assert InventoryHelper.has_all(inv, {"wood": 10, "stone": 5}) is True

    def test_has_all_insufficient(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5})
        assert InventoryHelper.has_all(inv, {"wood": 10, "stone": 6}) is False

    def test_has_all_missing(self) -> None:
        inv = Inventory(slots={"wood": 10})
        assert InventoryHelper.has_all(inv, {"wood": 5, "stone": 1}) is False

    def test_has_all_empty_requirements(self) -> None:
        inv = Inventory(slots={"wood": 10})
        assert InventoryHelper.has_all(inv, {}) is True


class TestInventoryHelperTransfer:
    def test_transfer_full_amount(self) -> None:
        source = Inventory(slots={"wood": 10})
        target = Inventory()
        transferred = InventoryHelper.transfer(source, target, "wood", 5)
        assert transferred == 5
        assert source.slots["wood"] == 5
        assert target.slots["wood"] == 5

    def test_transfer_limited_by_source(self) -> None:
        source = Inventory(slots={"wood": 3})
        target = Inventory()
        transferred = InventoryHelper.transfer(source, target, "wood", 10)
        assert transferred == 3
        assert "wood" not in source.slots
        assert target.slots["wood"] == 3

    def test_transfer_limited_by_target_capacity(self) -> None:
        source = Inventory(slots={"wood": 50})
        target = Inventory(capacity=10)
        transferred = InventoryHelper.transfer(source, target, "wood", 20)
        assert transferred == 10
        assert source.slots["wood"] == 40  # 50 - 10 (excess returned to source)
        assert target.slots["wood"] == 10

    def test_transfer_nonexistent(self) -> None:
        source = Inventory()
        target = Inventory()
        transferred = InventoryHelper.transfer(source, target, "wood", 5)
        assert transferred == 0
        assert "wood" not in source.slots
        assert "wood" not in target.slots

    def test_transfer_zero(self) -> None:
        source = Inventory(slots={"wood": 10})
        target = Inventory()
        transferred = InventoryHelper.transfer(source, target, "wood", 0)
        assert transferred == 0
        assert source.slots["wood"] == 10
        assert "wood" not in target.slots

    def test_transfer_negative_raises(self) -> None:
        source = Inventory(slots={"wood": 10})
        target = Inventory()
        with pytest.raises(ValueError, match="amount must be >= 0"):
            InventoryHelper.transfer(source, target, "wood", -5)


class TestInventoryHelperNames:
    def test_names_empty(self) -> None:
        inv = Inventory()
        names = InventoryHelper.names(inv)
        assert names == []

    def test_names_multiple(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5, "gold": 3})
        names = InventoryHelper.names(inv)
        assert set(names) == {"wood", "stone", "gold"}


class TestInventoryHelperClear:
    def test_clear_specific_type(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5})
        InventoryHelper.clear(inv, "wood")
        assert "wood" not in inv.slots
        assert inv.slots["stone"] == 5

    def test_clear_nonexistent_no_error(self) -> None:
        inv = Inventory(slots={"wood": 10})
        InventoryHelper.clear(inv, "stone")
        assert inv.slots["wood"] == 10

    def test_clear_all(self) -> None:
        inv = Inventory(slots={"wood": 10, "stone": 5, "gold": 3})
        InventoryHelper.clear(inv)
        assert inv.slots == {}


class TestInventoryECSIntegration:
    def test_inventory_as_component(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        eid = engine.world.spawn()
        inv = Inventory(slots={"wood": 10})
        engine.world.attach(eid, inv)

        retrieved = engine.world.get(eid, Inventory)
        assert retrieved is inv
        assert retrieved.slots["wood"] == 10

    def test_inventory_query(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        engine.world.attach(e1, Inventory(slots={"wood": 10}))
        engine.world.attach(e2, Inventory(slots={"stone": 5}))

        results = list(engine.world.query(Inventory))
        assert len(results) == 2
