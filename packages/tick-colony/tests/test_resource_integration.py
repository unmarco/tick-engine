"""Tests for tick-resource integration in tick-colony."""

from tick import Engine
from tick_colony import (
    Inventory,
    InventoryHelper,
    Recipe,
    ResourceDef,
    ResourceRegistry,
    can_craft,
    craft,
    make_resource_decay_system,
    ColonySnapshot,
    register_colony_components,
)


class TestResourceIntegration:
    """Test tick-resource re-exports and colony integration."""

    def test_all_exports_importable(self):
        """All 8 tick-resource exports importable from tick_colony."""
        assert Inventory is not None
        assert InventoryHelper is not None
        assert Recipe is not None
        assert ResourceDef is not None
        assert ResourceRegistry is not None
        assert callable(can_craft)
        assert callable(craft)
        assert callable(make_resource_decay_system)

    def test_inventory_as_world_component(self):
        """Inventory as world component -- attach, query, get."""
        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        eid = engine.world.spawn()
        inv = Inventory(capacity=50)
        engine.world.attach(eid, inv)

        assert engine.world.has(eid, Inventory)
        got = engine.world.get(eid, Inventory)
        assert got.capacity == 50

    def test_inventory_auto_registered_by_colony(self):
        """Inventory included in register_colony_components."""
        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        # Attach without manual registration -- should not raise
        eid = engine.world.spawn()
        inv = Inventory(capacity=100)
        InventoryHelper.add(inv, "wood", 5)
        engine.world.attach(eid, inv)

        assert engine.world.has(eid, Inventory)
        got = engine.world.get(eid, Inventory)
        assert InventoryHelper.count(got, "wood") == 5

    def test_resource_decay_system(self):
        """make_resource_decay_system in engine -- decay_rate reduces quantity each tick."""
        reg = ResourceRegistry()
        reg.define(ResourceDef(name="food", decay_rate=1))

        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        eid = engine.world.spawn()
        inv = Inventory(capacity=100)
        InventoryHelper.add(inv, "food", 10)
        engine.world.attach(eid, inv)

        engine.add_system(make_resource_decay_system(reg))

        # Step 1: food 10 -> 9
        engine.step()
        assert InventoryHelper.count(inv, "food") == 9

        # Step 2: food 9 -> 8
        engine.step()
        assert InventoryHelper.count(inv, "food") == 8

    def test_resource_registry_snapshot_via_colony_snapshot(self):
        """ResourceRegistry snapshot roundtrip via ColonySnapshot."""
        reg = ResourceRegistry()
        reg.define(ResourceDef(name="food", max_stack=100, decay_rate=1))
        reg.define(ResourceDef(name="wood"))

        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        snapper = ColonySnapshot(resource_registry=reg)
        data = snapper.snapshot(engine)
        assert "resource_registry" in data["colony"]

        # Restore into fresh registry
        reg2 = ResourceRegistry()
        engine2 = Engine(tps=20, seed=42)
        snapper2 = ColonySnapshot(resource_registry=reg2)
        snapper2.restore(engine2, data)

        assert reg2.has("food")
        assert reg2.has("wood")

        # Verify definitions match
        food_def = reg2.get("food")
        assert food_def.max_stack == 100
        assert food_def.decay_rate == 1

        wood_def = reg2.get("wood")
        assert wood_def.name == "wood"

    def test_recipe_crafting_with_inventory(self):
        """Recipe crafting consumes inputs and produces outputs."""
        inv = Inventory(capacity=100)
        InventoryHelper.add(inv, "wood", 5)
        InventoryHelper.add(inv, "stone", 3)

        recipe = Recipe(
            name="tool",
            inputs={"wood": 2, "stone": 1},
            outputs={"tool": 1},
        )

        assert can_craft(inv, recipe)
        result = craft(inv, recipe)
        assert result is True
        assert InventoryHelper.count(inv, "tool") == 1
        assert InventoryHelper.count(inv, "wood") == 3
        assert InventoryHelper.count(inv, "stone") == 2

        # Can craft again (still have 3 wood, 2 stone)
        assert can_craft(inv, recipe)
        craft(inv, recipe)
        assert InventoryHelper.count(inv, "tool") == 2
        assert InventoryHelper.count(inv, "wood") == 1
        assert InventoryHelper.count(inv, "stone") == 1

        # Cannot craft a third time (only 1 wood, need 2)
        assert not can_craft(inv, recipe)
        result = craft(inv, recipe)
        assert result is False

    def test_colony_snapshot_without_resource_registry(self):
        """ColonySnapshot without resource_registry still works."""
        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        eid = engine.world.spawn()
        inv = Inventory(capacity=50)
        InventoryHelper.add(inv, "gold", 10)
        engine.world.attach(eid, inv)

        snapper = ColonySnapshot()
        snapshot = snapper.snapshot(engine)

        assert "colony" in snapshot
        assert "resource_registry" not in snapshot["colony"]

        # Restore should work without error
        engine2 = Engine(tps=20, seed=42)
        register_colony_components(engine2.world)
        snapper2 = ColonySnapshot()
        snapper2.restore(engine2, snapshot)

        assert engine2.world.alive(eid)
        got = engine2.world.get(eid, Inventory)
        assert InventoryHelper.count(got, "gold") == 10

    def test_decay_with_on_spoiled_callback(self):
        """Resource decay triggers on_spoiled callback."""
        reg = ResourceRegistry()
        reg.define(ResourceDef(name="food", decay_rate=2))

        engine = Engine(tps=20, seed=42)
        register_colony_components(engine.world)

        eid = engine.world.spawn()
        inv = Inventory(capacity=100)
        InventoryHelper.add(inv, "food", 5)
        engine.world.attach(eid, inv)

        spoiled = []

        def on_spoiled(world, ctx, entity_id, resource_name, amount_lost):
            spoiled.append((entity_id, resource_name, amount_lost))

        engine.add_system(make_resource_decay_system(reg, on_spoiled=on_spoiled))

        engine.step()

        assert len(spoiled) == 1
        assert spoiled[0] == (eid, "food", 2)
        assert InventoryHelper.count(inv, "food") == 3
