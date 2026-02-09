"""Integration tests for tick-resource."""
from __future__ import annotations

from tick import Engine
from tick_resource import (
    Inventory,
    InventoryHelper,
    Recipe,
    ResourceDef,
    ResourceRegistry,
    craft,
    make_resource_decay_system,
)


class TestCraftThenDecayWorkflow:
    def test_craft_then_decay(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="wheat", decay_rate=0))
        registry.define(ResourceDef(name="bread", decay_rate=1))

        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"wheat": 10})
        engine.world.attach(eid, inv)

        # Craft bread from wheat
        recipe = Recipe(name="bake_bread", inputs={"wheat": 3}, outputs={"bread": 1})
        craft(inv, recipe)
        assert inv.slots["wheat"] == 7
        assert inv.slots["bread"] == 1

        # Run engine to trigger decay
        engine.run(1)

        # Wheat doesn't decay, bread does
        assert inv.slots["wheat"] == 7
        assert "bread" not in inv.slots


class TestSnapshotRestoreFullState:
    def test_snapshot_restore_engine_and_registry(self) -> None:
        engine1 = Engine(tps=20, seed=42)
        engine1.world.register_component(Inventory)

        registry1 = ResourceRegistry()
        registry1.define(ResourceDef(name="wood", max_stack=99, decay_rate=0))
        registry1.define(ResourceDef(name="meat", max_stack=10, decay_rate=2))

        system = make_resource_decay_system(registry1)
        engine1.add_system(system)

        e1 = engine1.world.spawn()
        e2 = engine1.world.spawn()
        inv1 = Inventory(slots={"wood": 50, "meat": 8})
        inv2 = Inventory(slots={"wood": 20})
        engine1.world.attach(e1, inv1)
        engine1.world.attach(e2, inv2)

        engine1.run(3)

        # Take snapshots
        engine_snapshot = engine1.snapshot()
        registry_snapshot = registry1.snapshot()

        # Restore into new instances
        engine2 = Engine(tps=20, seed=99)
        engine2.world.register_component(Inventory)

        registry2 = ResourceRegistry()
        registry2.restore(registry_snapshot)

        system2 = make_resource_decay_system(registry2)
        engine2.add_system(system2)

        engine2.restore(engine_snapshot)

        # Verify state
        results = list(engine2.world.query(Inventory))
        assert len(results) == 2

        inv_data = {eid: inv for eid, (inv,) in results}
        wood_totals = sum(inv.slots.get("wood", 0) for inv in inv_data.values())
        meat_totals = sum(inv.slots.get("meat", 0) for inv in inv_data.values())

        assert wood_totals == 70  # 50 + 20
        assert meat_totals == 2  # 8 - 2 * 3


class TestTransferBetweenEntityInventories:
    def test_transfer_between_entities(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        player = engine.world.spawn()
        chest = engine.world.spawn()

        player_inv = Inventory(slots={"gold": 100, "wood": 50})
        chest_inv = Inventory(slots={"gold": 20}, capacity=100)

        engine.world.attach(player, player_inv)
        engine.world.attach(chest, chest_inv)

        # Transfer gold from player to chest
        transferred = InventoryHelper.transfer(player_inv, chest_inv, "gold", 30)
        assert transferred == 30
        assert player_inv.slots["gold"] == 70
        assert chest_inv.slots["gold"] == 50

        # Transfer wood from player to chest (limited by capacity)
        transferred = InventoryHelper.transfer(player_inv, chest_inv, "wood", 60)
        assert transferred == 50  # capacity allows only 50 more
        assert chest_inv.slots["wood"] == 50
        assert "wood" not in player_inv.slots  # All 50 transferred, slot cleared


class TestInventoryWithWorldQueryIteration:
    def test_query_and_iterate(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="ore", decay_rate=1))

        system = make_resource_decay_system(registry)
        engine.add_system(system)

        # Create multiple entities with inventories
        for i in range(5):
            eid = engine.world.spawn()
            inv = Inventory(slots={"ore": 10 + i})
            engine.world.attach(eid, inv)

        engine.run(2)

        # Query and verify decay applied to all
        total_ore = 0
        for eid, (inv,) in engine.world.query(Inventory):
            total_ore += inv.slots.get("ore", 0)

        # Initial: 10 + 11 + 12 + 13 + 14 = 60
        # After 2 ticks at decay_rate=1: 60 - 10 = 50
        assert total_ore == 50
