"""Tests for resource decay system."""
from __future__ import annotations

from tick import Engine
from tick_resource import Inventory, ResourceDef, ResourceRegistry, make_resource_decay_system


class TestDecayNoDecay:
    def test_unknown_resource_skipped(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"unknown": 10})
        engine.world.attach(eid, inv)

        engine.run(5)

        # Unknown resource not defined, so no decay
        assert inv.slots["unknown"] == 10

    def test_zero_decay_rate(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="stone", decay_rate=0))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"stone": 10})
        engine.world.attach(eid, inv)

        engine.run(5)

        assert inv.slots["stone"] == 10


class TestDecayBasic:
    def test_single_resource(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="meat", decay_rate=2))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"meat": 10})
        engine.world.attach(eid, inv)

        engine.run(3)

        # 10 - 2 * 3 = 4
        assert inv.slots["meat"] == 4

    def test_decay_to_zero_removes_slot(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="fish", decay_rate=5))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"fish": 10})
        engine.world.attach(eid, inv)

        engine.run(2)

        # 10 - 5 * 2 = 0 (slot removed)
        assert "fish" not in inv.slots

    def test_multiple_resources_mixed_decay(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="meat", decay_rate=2))
        registry.define(ResourceDef(name="wood", decay_rate=0))
        registry.define(ResourceDef(name="fish", decay_rate=3))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"meat": 10, "wood": 5, "fish": 10})
        engine.world.attach(eid, inv)

        engine.run(2)

        assert inv.slots["meat"] == 6  # 10 - 2 * 2
        assert inv.slots["wood"] == 5  # no decay
        assert inv.slots["fish"] == 4  # 10 - 3 * 2

    def test_decay_caps_at_zero(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="fruit", decay_rate=5))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"fruit": 3})
        engine.world.attach(eid, inv)

        engine.run(1)

        # 3 - 5 -> capped at 0, slot removed
        assert "fruit" not in inv.slots


class TestDecayCallback:
    def test_on_spoiled_fires(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="food", decay_rate=3))

        spoiled_events: list[tuple[int, str, int]] = []

        def on_spoiled(world, ctx, eid, resource_name, amount_lost):  # type: ignore[no-untyped-def]
            spoiled_events.append((eid, resource_name, amount_lost))

        system = make_resource_decay_system(registry, on_spoiled=on_spoiled)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"food": 10})
        engine.world.attach(eid, inv)

        engine.run(2)

        assert len(spoiled_events) == 2
        assert spoiled_events[0] == (eid, "food", 3)
        assert spoiled_events[1] == (eid, "food", 3)
        assert inv.slots["food"] == 4

    def test_on_spoiled_not_called_for_zero_decay(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="metal", decay_rate=0))

        spoiled_events: list[tuple[int, str, int]] = []

        def on_spoiled(world, ctx, eid, resource_name, amount_lost):  # type: ignore[no-untyped-def]
            spoiled_events.append((eid, resource_name, amount_lost))

        system = make_resource_decay_system(registry, on_spoiled=on_spoiled)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"metal": 10})
        engine.world.attach(eid, inv)

        engine.run(5)

        assert spoiled_events == []


class TestDecayMultipleEntities:
    def test_decay_affects_all(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="bread", decay_rate=1))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        inv1 = Inventory(slots={"bread": 10})
        inv2 = Inventory(slots={"bread": 5})
        inv3 = Inventory(slots={"bread": 8})

        engine.world.attach(e1, inv1)
        engine.world.attach(e2, inv2)
        engine.world.attach(e3, inv3)

        engine.run(3)

        assert inv1.slots["bread"] == 7  # 10 - 3
        assert inv2.slots["bread"] == 2  # 5 - 3
        assert inv3.slots["bread"] == 5  # 8 - 3


class TestDecayEdgeCases:
    def test_entity_without_inventory_ignored(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="food", decay_rate=1))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        # Spawn entity without inventory
        engine.world.spawn()

        # Should not crash
        engine.run(5)

    def test_empty_inventory_no_decay(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="food", decay_rate=1))
        system = make_resource_decay_system(registry)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={})
        engine.world.attach(eid, inv)

        engine.run(5)

        assert inv.slots == {}

    def test_system_without_callback(self) -> None:
        engine = Engine(tps=20, seed=42)
        engine.world.register_component(Inventory)

        registry = ResourceRegistry()
        registry.define(ResourceDef(name="veggie", decay_rate=2))
        system = make_resource_decay_system(registry, on_spoiled=None)
        engine.add_system(system)

        eid = engine.world.spawn()
        inv = Inventory(slots={"veggie": 10})
        engine.world.attach(eid, inv)

        # Should work without callback
        engine.run(2)
        assert inv.slots["veggie"] == 6
