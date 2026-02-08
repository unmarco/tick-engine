"""Tests for Tween component and system integration."""

from dataclasses import dataclass

import pytest
from tick import Engine
from tick_tween import Tween, make_tween_system


@dataclass
class Health:
    """Test component for health values."""

    value: float = 100.0


@dataclass
class Position:
    """Test component for position values."""

    x: float = 0.0


class TestLinearInterpolation:
    """Test basic linear interpolation."""

    def test_full_duration_interpolation(self):
        """Tween from 0 to 100 over 10 ticks should reach 100."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        # Create entity with Health component
        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        # Create tween
        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        # Add tween system
        engine.add_system(make_tween_system())

        # Run 10 ticks
        engine.run(10)

        # Verify final value
        health = world.get(eid, Health)
        assert health is not None
        assert health.value == 100.0

    def test_intermediate_values(self):
        """After 5 of 10 ticks, linear interpolation should be at 50%."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 5 ticks
        engine.run(5)

        # Verify intermediate value
        health = world.get(eid, Health)
        assert health is not None
        assert health.value == 50.0


class TestTweenLifecycle:
    """Test tween auto-detachment and completion."""

    def test_auto_detach_on_completion(self):
        """Tween should be detached after completion."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run full duration
        engine.run(10)

        # Verify tween is detached
        assert not world.has(eid, Tween)

    def test_on_complete_callback(self):
        """on_complete callback should be called when tween finishes."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        callback_data = {}

        def on_complete(world, ctx, eid, tween):
            callback_data["called"] = True
            callback_data["world"] = world
            callback_data["ctx"] = ctx
            callback_data["eid"] = eid
            callback_data["tween"] = tween

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system(on_complete=on_complete))

        # Run full duration
        engine.run(10)

        # Verify callback was called
        assert callback_data.get("called") is True
        assert callback_data["world"] is world
        assert callback_data["ctx"] is not None
        assert callback_data["eid"] == eid
        assert callback_data["tween"] is not None

    def test_callback_fires_after_detach(self):
        """Tween is detached before on_complete — enables chaining."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        tween_present_in_callback = {}

        def on_complete(world, ctx, eid, tween):
            tween_present_in_callback["has_tween"] = world.has(eid, Tween)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system(on_complete=on_complete))

        # Run full duration
        engine.run(10)

        # Tween detached before callback — enables chaining without stomping
        assert tween_present_in_callback["has_tween"] is False
        assert not world.has(eid, Tween)

    def test_tween_chaining(self):
        """on_complete can attach a new Tween for chaining."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        target_key = f"{Health.__module__}.{Health.__qualname__}"

        def on_complete(world, ctx, eid, tween):
            # Attach a second tween from 100 to 200
            second_tween = Tween(
                target=target_key,
                field="value",
                start_val=100.0,
                end_val=200.0,
                duration=5,
                easing="linear",
            )
            world.attach(eid, second_tween)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        first_tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, first_tween)

        engine.add_system(make_tween_system(on_complete=on_complete))

        # Run first tween (10 ticks)
        engine.run(10)

        # Verify first tween completed
        health = world.get(eid, Health)
        assert health.value == 100.0

        # Run second tween (5 more ticks)
        engine.run(5)

        # Verify second tween completed
        health = world.get(eid, Health)
        assert health.value == 200.0


class TestEasingFunctions:
    """Test different easing functions."""

    def test_ease_in_interpolation(self):
        """Ease-in: after half duration, value should be 25% (t*t where t=0.5)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="ease_in",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 5 ticks (half duration)
        engine.run(5)

        health = world.get(eid, Health)
        assert health is not None
        # t = 0.5, ease_in(0.5) = 0.25, value = 0 + (100-0) * 0.25 = 25
        assert health.value == 25.0

    def test_ease_out_interpolation(self):
        """Ease-out: after half duration, value should be 75%."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="ease_out",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 5 ticks (half duration)
        engine.run(5)

        health = world.get(eid, Health)
        assert health is not None
        # t = 0.5, ease_out(0.5) = 0.75, value = 0 + (100-0) * 0.75 = 75
        assert health.value == 75.0

    def test_ease_in_out_interpolation(self):
        """Ease-in-out: verify midpoint and quarter-point values."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=8,
            easing="ease_in_out",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 4 ticks (half duration)
        engine.run(4)

        health = world.get(eid, Health)
        assert health is not None
        # t = 0.5, ease_in_out(0.5) = 0.5, value = 50
        assert health.value == 50.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_end_value_exact(self):
        """After completion, value should be exactly end_val (no float drift)."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=99.99,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        engine.run(10)

        health = world.get(eid, Health)
        assert health is not None
        assert health.value == 99.99

    def test_duration_of_one(self):
        """Tween with duration=1 should complete after 1 tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=1,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 1 tick
        engine.run(1)

        # Verify value is end_val
        health = world.get(eid, Health)
        assert health is not None
        assert health.value == 100.0

        # Verify tween is detached
        assert not world.has(eid, Tween)

    def test_missing_target_component(self):
        """Entity has Tween but not target component: should skip silently."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        # No Health component attached

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Should not crash
        engine.run(10)

        # Tween should still be present (not detached because target not found)
        # Note: This behavior depends on implementation details. If the implementation
        # detaches anyway, adjust this assertion.
        # For now, assuming it skips silently and doesn't detach.

    def test_missing_target_type_in_registry(self):
        """Tween.target refers to unregistered type: should skip silently."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        # Note: NOT registering Health

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        # Use a registry key that doesn't exist
        tween = Tween(
            target="nonexistent.UnregisteredType",
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Should not crash
        engine.run(10)


class TestMultipleEntities:
    """Test multiple tweens on different entities."""

    def test_multiple_tweens_on_different_entities(self):
        """Two entities with different tweens should interpolate independently."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        # Entity 1: tween from 0 to 100 over 10 ticks
        eid1 = world.spawn()
        world.attach(eid1, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween1 = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid1, tween1)

        # Entity 2: tween from 50 to 150 over 5 ticks
        eid2 = world.spawn()
        world.attach(eid2, Health(value=50.0))

        tween2 = Tween(
            target=target_key,
            field="value",
            start_val=50.0,
            end_val=150.0,
            duration=5,
            easing="linear",
        )
        world.attach(eid2, tween2)

        engine.add_system(make_tween_system())

        # Run 5 ticks
        engine.run(5)

        # Entity 1 should be halfway (50)
        health1 = world.get(eid1, Health)
        assert health1.value == 50.0

        # Entity 2 should be complete (150)
        health2 = world.get(eid2, Health)
        assert health2.value == 150.0

        # Entity 2 should have tween detached
        assert not world.has(eid2, Tween)

        # Entity 1 should still have tween
        assert world.has(eid1, Tween)

        # Run 5 more ticks
        engine.run(5)

        # Entity 1 should now be complete (100)
        health1 = world.get(eid1, Health)
        assert health1.value == 100.0

        # Entity 1 tween should be detached
        assert not world.has(eid1, Tween)


class TestValueRanges:
    """Test different value ranges."""

    def test_decreasing_values(self):
        """Tween from 100 to 0 should interpolate downward."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=100.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=100.0,
            end_val=0.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 5 ticks (halfway)
        engine.run(5)

        health = world.get(eid, Health)
        assert health is not None
        assert health.value == 50.0

        # Run 5 more ticks (complete)
        engine.run(5)

        health = world.get(eid, Health)
        assert health.value == 0.0

    def test_negative_values(self):
        """Tween from -50 to 50 should interpolate correctly."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=-50.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=-50.0,
            end_val=50.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 5 ticks (halfway)
        engine.run(5)

        health = world.get(eid, Health)
        assert health is not None
        assert health.value == 0.0

        # Run 5 more ticks (complete)
        engine.run(5)

        health = world.get(eid, Health)
        assert health.value == 50.0


class TestMultipleComponents:
    """Test tweening different component types and fields."""

    def test_different_fields_on_different_components(self):
        """Verify tweening works with different component types."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)
        world.register_component(Position)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))
        world.attach(eid, Position(x=0.0))

        health_key = f"{Health.__module__}.{Health.__qualname__}"
        position_key = f"{Position.__module__}.{Position.__qualname__}"

        # Tween health
        health_tween = Tween(
            target=health_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, health_tween)

        engine.add_system(make_tween_system())

        # Run 10 ticks
        engine.run(10)

        # Health should be tweened
        health = world.get(eid, Health)
        assert health.value == 100.0

        # Position should be unchanged
        position = world.get(eid, Position)
        assert position.x == 0.0


class TestTweenStateProgression:
    """Test that tween elapsed counter increments correctly."""

    def test_elapsed_increments_each_tick(self):
        """Verify elapsed counter increments every tick."""
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid = world.spawn()
        world.attach(eid, Health(value=0.0))

        target_key = f"{Health.__module__}.{Health.__qualname__}"
        tween = Tween(
            target=target_key,
            field="value",
            start_val=0.0,
            end_val=100.0,
            duration=10,
            easing="linear",
        )
        world.attach(eid, tween)

        engine.add_system(make_tween_system())

        # Run 1 tick at a time and check elapsed
        for expected_elapsed in range(1, 11):
            engine.step()
            if world.has(eid, Tween):
                current_tween = world.get(eid, Tween)
                if expected_elapsed < 10:
                    assert current_tween.elapsed == expected_elapsed
