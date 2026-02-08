"""Tests for tick_colony.needs module - decaying drives."""

import pytest
from tick_colony import NeedSet, NeedHelper, make_need_decay_system
from tick import Engine


class TestNeedSet:
    def test_needset_creation_with_flat_data(self):
        need_set = NeedSet(data={
            "hunger": [100.0, 100.0, 1.0, 20.0],
            "thirst": [50.0, 100.0, 2.0, 15.0],
        })
        assert "hunger" in need_set.data
        assert "thirst" in need_set.data
        assert need_set.data["hunger"] == [100.0, 100.0, 1.0, 20.0]

    def test_needset_empty_data(self):
        need_set = NeedSet(data={})
        assert need_set.data == {}


class TestNeedHelper:
    def test_add_need(self):
        need_set = NeedSet(data={})
        NeedHelper.add(need_set, "energy", value=80.0, max_val=100.0, decay_rate=0.5, critical_threshold=25.0)

        assert "energy" in need_set.data
        assert need_set.data["energy"] == [80.0, 100.0, 0.5, 25.0]

    def test_get_value(self):
        need_set = NeedSet(data={"hunger": [75.0, 100.0, 1.0, 20.0]})
        value = NeedHelper.get_value(need_set, "hunger")
        assert value == 75.0

    def test_set_value(self):
        need_set = NeedSet(data={"hunger": [50.0, 100.0, 1.0, 20.0]})
        NeedHelper.set_value(need_set, "hunger", 90.0)
        assert need_set.data["hunger"][0] == 90.0

    def test_set_value_clamping_to_zero(self):
        need_set = NeedSet(data={"hunger": [50.0, 100.0, 1.0, 20.0]})
        NeedHelper.set_value(need_set, "hunger", -10.0)
        assert need_set.data["hunger"][0] == 0.0

    def test_set_value_clamping_to_max(self):
        need_set = NeedSet(data={"hunger": [50.0, 100.0, 1.0, 20.0]})
        NeedHelper.set_value(need_set, "hunger", 150.0)
        assert need_set.data["hunger"][0] == 100.0

    def test_is_critical_true(self):
        need_set = NeedSet(data={"hunger": [15.0, 100.0, 1.0, 20.0]})
        assert NeedHelper.is_critical(need_set, "hunger") is True

    def test_is_critical_false(self):
        need_set = NeedSet(data={"hunger": [50.0, 100.0, 1.0, 20.0]})
        assert NeedHelper.is_critical(need_set, "hunger") is False

    def test_is_critical_at_threshold(self):
        need_set = NeedSet(data={"hunger": [20.0, 100.0, 1.0, 20.0]})
        assert NeedHelper.is_critical(need_set, "hunger") is True

    def test_names(self):
        need_set = NeedSet(data={
            "hunger": [100.0, 100.0, 1.0, 20.0],
            "thirst": [100.0, 100.0, 2.0, 15.0],
            "rest": [100.0, 100.0, 0.5, 30.0],
        })
        names = NeedHelper.names(need_set)
        assert set(names) == {"hunger", "thirst", "rest"}


class TestNeedDecaySystem:
    def test_values_decay_each_tick(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [100.0, 100.0, 5.0, 20.0]})
        world.attach(e1, need_set)

        decay_system = make_need_decay_system()
        engine.add_system(decay_system)

        engine.step()
        assert NeedHelper.get_value(need_set, "hunger") == 95.0

        engine.step()
        assert NeedHelper.get_value(need_set, "hunger") == 90.0

        engine.step()
        assert NeedHelper.get_value(need_set, "hunger") == 85.0

    def test_decay_clamped_to_zero(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [3.0, 100.0, 5.0, 20.0]})
        world.attach(e1, need_set)

        decay_system = make_need_decay_system()
        engine.add_system(decay_system)

        engine.step()
        assert NeedHelper.get_value(need_set, "hunger") == 0.0

        engine.step()
        assert NeedHelper.get_value(need_set, "hunger") == 0.0  # Stays at 0

    def test_on_critical_fires_on_transition(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [25.0, 100.0, 10.0, 20.0]})
        world.attach(e1, need_set)

        critical_events = []

        def on_critical(world, ctx, entity_id, need_name):
            critical_events.append((ctx.tick_number, entity_id, need_name))

        decay_system = make_need_decay_system(on_critical=on_critical)
        engine.add_system(decay_system)

        engine.step()  # hunger becomes 15.0, crosses threshold
        assert len(critical_events) == 1
        assert critical_events[0] == (1, e1, "hunger")

        engine.step()  # hunger becomes 5.0, still critical but no new event
        assert len(critical_events) == 1  # Should not fire again

    def test_on_critical_not_fired_every_tick_while_critical(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [10.0, 100.0, 2.0, 20.0]})  # Already critical
        world.attach(e1, need_set)

        critical_events = []

        def on_critical(world, ctx, entity_id, need_name):
            critical_events.append((ctx.tick_number, entity_id, need_name))

        decay_system = make_need_decay_system(on_critical=on_critical)
        engine.add_system(decay_system)

        engine.step()  # Still critical, was already critical
        engine.step()
        engine.step()

        # Should not fire because it was already critical
        assert len(critical_events) == 0

    def test_multiple_needs_decaying_independently(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={
            "hunger": [100.0, 100.0, 5.0, 20.0],
            "thirst": [100.0, 100.0, 10.0, 15.0],
            "rest": [100.0, 100.0, 2.0, 30.0],
        })
        world.attach(e1, need_set)

        decay_system = make_need_decay_system()
        engine.add_system(decay_system)

        engine.step()

        assert NeedHelper.get_value(need_set, "hunger") == 95.0
        assert NeedHelper.get_value(need_set, "thirst") == 90.0
        assert NeedHelper.get_value(need_set, "rest") == 98.0

    def test_multiple_entities_with_needs(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        e2 = world.spawn()

        world.attach(e1, NeedSet(data={"hunger": [50.0, 100.0, 5.0, 20.0]}))
        world.attach(e2, NeedSet(data={"thirst": [60.0, 100.0, 3.0, 15.0]}))

        decay_system = make_need_decay_system()
        engine.add_system(decay_system)

        engine.step()

        ns1 = world.get(e1, NeedSet)
        ns2 = world.get(e2, NeedSet)

        assert NeedHelper.get_value(ns1, "hunger") == 45.0
        assert NeedHelper.get_value(ns2, "thirst") == 57.0

    def test_on_critical_with_multiple_needs_transitioning(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={
            "hunger": [25.0, 100.0, 10.0, 20.0],  # Will transition
            "thirst": [18.0, 100.0, 5.0, 15.0],   # Will transition
            "rest": [50.0, 100.0, 1.0, 30.0],     # Won't transition
        })
        world.attach(e1, need_set)

        critical_events = []

        def on_critical(world, ctx, entity_id, need_name):
            critical_events.append(need_name)

        decay_system = make_need_decay_system(on_critical=on_critical)
        engine.add_system(decay_system)

        engine.step()

        assert len(critical_events) == 2
        assert "hunger" in critical_events
        assert "thirst" in critical_events
        assert "rest" not in critical_events

    def test_need_decay_system_with_no_callback(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [25.0, 100.0, 10.0, 20.0]})
        world.attach(e1, need_set)

        decay_system = make_need_decay_system()  # No on_critical
        engine.add_system(decay_system)

        engine.step()  # Should not crash
        assert NeedHelper.get_value(need_set, "hunger") == 15.0

    def test_on_zero_fires_on_transition(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [0.5, 100.0, 1.0, 20.0]})
        world.attach(e1, need_set)

        zero_events = []

        def on_zero(world, ctx, entity_id, need_name):
            zero_events.append((ctx.tick_number, entity_id, need_name))

        decay_system = make_need_decay_system(on_zero=on_zero)
        engine.add_system(decay_system)

        engine.step()  # hunger becomes 0.0 (was 0.5, decayed by 1.0)
        assert len(zero_events) == 1
        assert zero_events[0] == (1, e1, "hunger")
        assert NeedHelper.get_value(need_set, "hunger") == 0.0

    def test_on_zero_does_not_fire_while_already_zero(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [0.0, 100.0, 1.0, 20.0]})  # Already at zero
        world.attach(e1, need_set)

        zero_events = []

        def on_zero(world, ctx, entity_id, need_name):
            zero_events.append((ctx.tick_number, entity_id, need_name))

        decay_system = make_need_decay_system(on_zero=on_zero)
        engine.add_system(decay_system)

        engine.step()
        engine.step()
        engine.step()

        # Should not fire because was_above_zero is False
        assert len(zero_events) == 0
        assert NeedHelper.get_value(need_set, "hunger") == 0.0

    def test_on_zero_and_on_critical_coexist(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={"hunger": [25.0, 100.0, 5.0, 20.0]})
        world.attach(e1, need_set)

        critical_events = []
        zero_events = []

        def on_critical(world, ctx, entity_id, need_name):
            critical_events.append((ctx.tick_number, entity_id, need_name))

        def on_zero(world, ctx, entity_id, need_name):
            zero_events.append((ctx.tick_number, entity_id, need_name))

        decay_system = make_need_decay_system(on_critical=on_critical, on_zero=on_zero)
        engine.add_system(decay_system)

        engine.step()  # hunger becomes 20.0, transitions to critical
        assert len(critical_events) == 1
        assert critical_events[0] == (1, e1, "hunger")
        assert len(zero_events) == 0

        engine.run(3)  # hunger becomes 15.0, 10.0, 5.0
        assert len(critical_events) == 1  # Still only one critical event
        assert len(zero_events) == 0

        engine.step()  # hunger becomes 0.0, transitions to zero
        assert len(critical_events) == 1
        assert len(zero_events) == 1
        assert zero_events[0] == (5, e1, "hunger")

    def test_on_zero_breaks_inner_loop(self):
        engine = Engine(tps=20, seed=42)
        world = engine.world

        e1 = world.spawn()
        need_set = NeedSet(data={
            "hunger": [0.3, 100.0, 1.0, 20.0],
            "fatigue": [0.3, 100.0, 1.0, 20.0],
        })
        world.attach(e1, need_set)

        zero_events = []

        def on_zero(world, ctx, entity_id, need_name):
            zero_events.append((ctx.tick_number, entity_id, need_name))

        decay_system = make_need_decay_system(on_zero=on_zero)
        engine.add_system(decay_system)

        engine.step()  # Both needs decay to 0.0, but break after first

        # Only one on_zero event should fire (break after first)
        assert len(zero_events) == 1
        # Either hunger or fatigue could fire first (dict iteration order)
        fired_need = zero_events[0][2]
        assert fired_need in ["hunger", "fatigue"]
        assert zero_events[0] == (1, e1, fired_need)
