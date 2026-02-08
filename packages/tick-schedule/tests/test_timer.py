"""Tests for Timer component and make_timer_system."""
import dataclasses

import pytest
from tick import Engine

from tick_schedule import Timer, make_timer_system


class TestTimerBasics:
    """Basic Timer behavior tests."""

    def test_timer_fires_at_correct_tick(self):
        """Timer(remaining=5) fires after exactly 5 ticks."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append((ctx.tick_number, eid, timer.name))

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="build", remaining=5))

        # Tick 1-4: should not fire yet
        engine.run(4)
        assert len(fired) == 0

        # Tick 5: should fire
        engine.step()
        assert len(fired) == 1
        assert fired[0] == (5, eid, "build")

    def test_timer_fires_exactly_once(self):
        """on_fire called exactly once, not on subsequent ticks."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append((ctx.tick_number, eid, timer.name))

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="test", remaining=3))

        # Run 10 ticks total
        engine.run(10)

        # Should fire exactly once at tick 3
        assert len(fired) == 1
        assert fired[0][0] == 3

    def test_timer_auto_detaches(self):
        """Entity no longer has Timer after fire."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append(eid)

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="test", remaining=2))

        # Before firing: has Timer
        assert world.has(eid, Timer)

        # Run until after fire
        engine.run(3)

        # After firing: no Timer
        assert not world.has(eid, Timer)
        assert len(fired) == 1

    def test_timer_remaining_1_fires_next_tick(self):
        """Timer with remaining=1 fires on the very next tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append(ctx.tick_number)

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="fast", remaining=1))

        # Should fire on tick 1
        engine.step()
        assert len(fired) == 1
        assert fired[0] == 1

    def test_timer_remaining_decrements_each_tick(self):
        """Check intermediate state as remaining decrements."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        # No-op callback
        system = make_timer_system(lambda w, c, e, t: None)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="test", remaining=5))

        # Initial state
        timer = world.get(eid, Timer)
        assert timer.remaining == 5

        # After tick 1: remaining=4
        engine.step()
        timer = world.get(eid, Timer)
        assert timer.remaining == 4

        # After tick 2: remaining=3
        engine.step()
        timer = world.get(eid, Timer)
        assert timer.remaining == 3

        # After tick 3: remaining=2
        engine.step()
        timer = world.get(eid, Timer)
        assert timer.remaining == 2

        # After tick 4: remaining=1
        engine.step()
        timer = world.get(eid, Timer)
        assert timer.remaining == 1

        # After tick 5: detached
        engine.step()
        assert not world.has(eid, Timer)


class TestTimerCallbacks:
    """Tests for Timer callback behavior."""

    def test_timer_callback_receives_correct_args(self):
        """Callback receives world, ctx, eid, timer all correctly."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        received_args = []

        def on_fire(w, ctx, eid, timer):
            received_args.append({
                'world': w,
                'tick_number': ctx.tick_number,
                'eid': eid,
                'timer_name': timer.name,
                'timer_remaining': timer.remaining,
            })

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="callback_test", remaining=2))

        engine.run(3)

        assert len(received_args) == 1
        args = received_args[0]
        assert args['world'] is world
        assert args['tick_number'] == 2
        assert args['eid'] == eid
        assert args['timer_name'] == "callback_test"
        assert args['timer_remaining'] == 0  # Decremented before fire

    def test_timer_callback_can_attach_new_timer(self):
        """Callback can attach new Timer to the same entity (chaining)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append(timer.name)
            if timer.name == "first":
                # Attach a new timer after first fires
                w.attach(eid, Timer(name="second", remaining=3))

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="first", remaining=2))

        # Tick 1-2: first timer counting down
        engine.run(2)
        assert fired == ["first"]
        assert world.has(eid, Timer)  # Second timer now attached

        # Tick 3-5: second timer counting down
        engine.run(3)
        assert fired == ["first", "second"]
        assert not world.has(eid, Timer)  # Second timer also fired and detached


class TestTimerMultipleEntities:
    """Tests with multiple entities having Timers."""

    def test_multiple_entities_with_timers(self):
        """Each entity fires independently at correct time."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append((ctx.tick_number, eid, timer.name))

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid1 = world.spawn()
        eid2 = world.spawn()
        eid3 = world.spawn()

        world.attach(eid1, Timer(name="fast", remaining=2))
        world.attach(eid2, Timer(name="medium", remaining=5))
        world.attach(eid3, Timer(name="slow", remaining=8))

        engine.run(10)

        # All three should fire at different ticks
        assert len(fired) == 3
        assert (2, eid1, "fast") in fired
        assert (5, eid2, "medium") in fired
        assert (8, eid3, "slow") in fired

        # All should be detached
        assert not world.has(eid1, Timer)
        assert not world.has(eid2, Timer)
        assert not world.has(eid3, Timer)

    def test_timer_with_different_names(self):
        """Timer name is preserved in callback."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired_names = []

        def on_fire(w, ctx, eid, timer):
            fired_names.append(timer.name)

        system = make_timer_system(on_fire)
        engine.add_system(system)

        names = ["build", "heal", "attack", "craft"]
        eids = []

        for i, name in enumerate(names, start=1):
            eid = world.spawn()
            eids.append(eid)
            world.attach(eid, Timer(name=name, remaining=i))

        engine.run(5)

        # All timers should have fired with correct names
        assert len(fired_names) == 4
        assert set(fired_names) == set(names)


class TestTimerSerialization:
    """Tests for Timer snapshot/restore."""

    def test_timer_serialization_round_trip(self):
        """Timer state survives snapshot/restore."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append((ctx.tick_number, eid, timer.name))

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="persist", remaining=7))

        # Run 3 ticks
        engine.run(3)
        assert len(fired) == 0

        # Snapshot
        snapshot = world.snapshot()

        # Restore to new engine
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        world2.register_component(Timer)
        world2.restore(snapshot)

        # Re-add system
        fired2 = []

        def on_fire2(w, ctx, eid, timer):
            fired2.append((ctx.tick_number, eid, timer.name))

        system2 = make_timer_system(on_fire2)
        engine2.add_system(system2)

        # Timer should have remaining=4 (7-3)
        timer = world2.get(eid, Timer)
        assert timer.remaining == 4
        assert timer.name == "persist"

        # Run 4 more ticks in restored engine
        engine2.run(4)

        # Should fire at tick 4 in the new engine
        assert len(fired2) == 1
        assert fired2[0][0] == 4
        assert fired2[0][1] == eid
        assert fired2[0][2] == "persist"

    def test_timer_serialization_preserves_multiple_timers(self):
        """Multiple Timers serialize and restore correctly."""
        engine = Engine(tps=20, seed=42)
        world = engine.world

        system = make_timer_system(lambda w, c, e, t: None)
        engine.add_system(system)

        eid1 = world.spawn()
        eid2 = world.spawn()
        eid3 = world.spawn()

        world.attach(eid1, Timer(name="alpha", remaining=5))
        world.attach(eid2, Timer(name="beta", remaining=3))
        world.attach(eid3, Timer(name="gamma", remaining=8))

        # Run 2 ticks
        engine.run(2)

        # Snapshot
        snapshot = world.snapshot()

        # Restore
        engine2 = Engine(tps=20, seed=42)
        world2 = engine2.world
        world2.register_component(Timer)
        world2.restore(snapshot)

        # Verify all timers restored with correct state
        timer1 = world2.get(eid1, Timer)
        assert timer1.name == "alpha"
        assert timer1.remaining == 3  # 5-2

        timer2 = world2.get(eid2, Timer)
        assert timer2.name == "beta"
        assert timer2.remaining == 1  # 3-2

        timer3 = world2.get(eid3, Timer)
        assert timer3.name == "gamma"
        assert timer3.remaining == 6  # 8-2


class TestTimerEdgeCases:
    """Edge case and boundary tests."""

    def test_timer_remaining_zero_immediate(self):
        """Timer with remaining=0 fires immediately on first tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append(ctx.tick_number)

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="instant", remaining=0))

        engine.step()

        # Should fire on tick 1 (remaining becomes -1)
        assert len(fired) == 1
        assert fired[0] == 1

    def test_timer_callback_can_despawn_entity(self):
        """Callback can safely despawn the entity."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append(eid)
            w.despawn(eid)

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="boom", remaining=3))

        engine.run(5)

        # Should have fired and despawned
        assert len(fired) == 1
        assert fired[0] == eid
        # Entity should not exist
        # (Note: tick engine doesn't have has_entity, but we can verify no components)
        assert not world.has(eid, Timer)

    def test_timer_with_no_callback_fires(self):
        """System works even with minimal callback."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        call_count = [0]

        def on_fire(w, ctx, eid, timer):
            call_count[0] += 1

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid = world.spawn()
        world.attach(eid, Timer(name="minimal", remaining=2))

        engine.run(3)

        assert call_count[0] == 1
        assert not world.has(eid, Timer)

    def test_multiple_timers_same_tick(self):
        """Multiple timers can fire on the same tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        fired = []

        def on_fire(w, ctx, eid, timer):
            fired.append((ctx.tick_number, eid, timer.name))

        system = make_timer_system(on_fire)
        engine.add_system(system)

        eid1 = world.spawn()
        eid2 = world.spawn()
        eid3 = world.spawn()

        # All fire on tick 5
        world.attach(eid1, Timer(name="one", remaining=5))
        world.attach(eid2, Timer(name="two", remaining=5))
        world.attach(eid3, Timer(name="three", remaining=5))

        engine.run(6)

        assert len(fired) == 3
        # All fired on tick 5
        assert all(tick == 5 for tick, _, _ in fired)
        # All different entities
        eids = {eid for _, eid, _ in fired}
        assert eids == {eid1, eid2, eid3}
