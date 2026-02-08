"""Tests for tick_colony.lifecycle module - age-based entity despawning."""

import pytest
from tick_colony.lifecycle import Lifecycle, make_lifecycle_system
from tick import Engine


class TestLifecycleComponent:
    def test_lifecycle_component_creation(self):
        lifecycle = Lifecycle(born_tick=5, max_age=100)
        assert lifecycle.born_tick == 5
        assert lifecycle.max_age == 100


class TestLifecycleSystem:
    def test_lifecycle_immortal_never_dies(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        deaths = []

        def on_death(world, ctx, eid, cause):
            deaths.append((eid, cause, ctx.tick_number))

        engine.add_system(make_lifecycle_system(on_death=on_death))

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=0, max_age=-1))

        engine.run(100)

        assert engine.world.alive(eid)
        assert len(deaths) == 0

    def test_lifecycle_death_at_correct_tick(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        deaths = []

        def on_death(world, ctx, eid, cause):
            deaths.append((eid, cause, ctx.tick_number))

        engine.add_system(make_lifecycle_system(on_death=on_death))

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=0, max_age=10))

        engine.run(9)
        assert engine.world.alive(eid)

        engine.step()  # tick 10
        assert not engine.world.alive(eid)
        assert deaths == [(eid, "old_age", 10)]

    def test_lifecycle_on_death_callback_fires(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        callback_invocations = []

        def on_death(world, ctx, eid, cause):
            callback_invocations.append({
                "world": world,
                "ctx": ctx,
                "entity_id": eid,
                "cause": cause,
            })

        engine.add_system(make_lifecycle_system(on_death=on_death))

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=0, max_age=5))

        engine.run(5)

        assert len(callback_invocations) == 1
        params = callback_invocations[0]
        assert params["world"] is engine.world
        assert params["ctx"].tick_number == 5
        assert params["entity_id"] == eid
        assert params["cause"] == "old_age"

    def test_lifecycle_entity_despawned_after_death(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        engine.add_system(make_lifecycle_system())

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=0, max_age=3))

        assert engine.world.alive(eid)
        engine.run(3)
        assert not engine.world.alive(eid)

    def test_lifecycle_multiple_entities_different_ages(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        deaths = []

        def on_death(world, ctx, eid, cause):
            deaths.append((eid, ctx.tick_number))

        engine.add_system(make_lifecycle_system(on_death=on_death))

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        engine.world.attach(e1, Lifecycle(born_tick=0, max_age=5))
        engine.world.attach(e2, Lifecycle(born_tick=0, max_age=10))

        engine.run(5)
        assert not engine.world.alive(e1)
        assert engine.world.alive(e2)
        assert len(deaths) == 1
        assert deaths[0] == (e1, 5)

        engine.run(5)  # Total 10 ticks
        assert not engine.world.alive(e2)
        assert len(deaths) == 2
        assert deaths[1] == (e2, 10)

    def test_lifecycle_born_later(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        deaths = []

        def on_death(world, ctx, eid, cause):
            deaths.append((eid, ctx.tick_number))

        engine.add_system(make_lifecycle_system(on_death=on_death))

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=5, max_age=10))

        engine.run(14)
        assert engine.world.alive(eid)

        engine.step()  # tick 15: 15 - 5 = 10, equals max_age
        assert not engine.world.alive(eid)
        assert deaths == [(eid, 15)]

    def test_lifecycle_zero_max_age_treated_as_immortal(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        deaths = []

        def on_death(world, ctx, eid, cause):
            deaths.append((eid, cause, ctx.tick_number))

        engine.add_system(make_lifecycle_system(on_death=on_death))

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=0, max_age=0))

        engine.run(50)

        assert engine.world.alive(eid)
        assert len(deaths) == 0

    def test_lifecycle_system_with_no_callback(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        engine.add_system(make_lifecycle_system())  # No on_death callback

        eid = engine.world.spawn()
        engine.world.attach(eid, Lifecycle(born_tick=0, max_age=5))

        engine.run(5)  # Should not crash
        assert not engine.world.alive(eid)

    def test_lifecycle_multiple_entities_simultaneous_death(self):
        engine = Engine(tps=1, seed=42)
        engine.world.register_component(Lifecycle)

        deaths = []

        def on_death(world, ctx, eid, cause):
            deaths.append(eid)

        engine.add_system(make_lifecycle_system(on_death=on_death))

        e1 = engine.world.spawn()
        e2 = engine.world.spawn()
        e3 = engine.world.spawn()

        engine.world.attach(e1, Lifecycle(born_tick=0, max_age=7))
        engine.world.attach(e2, Lifecycle(born_tick=0, max_age=7))
        engine.world.attach(e3, Lifecycle(born_tick=0, max_age=7))

        engine.run(7)

        assert len(deaths) == 3
        assert e1 in deaths
        assert e2 in deaths
        assert e3 in deaths
        assert not engine.world.alive(e1)
        assert not engine.world.alive(e2)
        assert not engine.world.alive(e3)
