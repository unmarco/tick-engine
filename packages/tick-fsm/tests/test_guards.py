"""Tests for FSMGuards registry."""
import pytest
from tick import Engine
from tick_fsm import FSMGuards


class TestFSMGuardsRegistry:
    """Test cases for FSMGuards registry."""

    def test_register_and_check(self):
        """Register a guard, check returns correct bool."""
        # Arrange
        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        eid = world.spawn()

        # Register a guard that always returns True
        guards.register("always_true", lambda w, e: True)

        # Act & Assert
        assert guards.check("always_true", world, eid) is True

        # Register a guard that always returns False
        guards.register("always_false", lambda w, e: False)
        assert guards.check("always_false", world, eid) is False

    def test_unregistered_guard_raises_keyerror(self):
        """Check with unknown name raises KeyError."""
        # Arrange
        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        eid = world.spawn()

        # Act & Assert
        with pytest.raises(KeyError):
            guards.check("nonexistent", world, eid)

    def test_has_method(self):
        """Has returns True for registered, False for unregistered."""
        # Arrange
        guards = FSMGuards()
        guards.register("exists", lambda w, e: True)

        # Act & Assert
        assert guards.has("exists") is True
        assert guards.has("does_not_exist") is False

    def test_names_method(self):
        """Returns list of all registered guard names."""
        # Arrange
        guards = FSMGuards()
        guards.register("guard1", lambda w, e: True)
        guards.register("guard2", lambda w, e: False)
        guards.register("guard3", lambda w, e: True)

        # Act
        names = guards.names()

        # Assert
        assert len(names) == 3
        assert "guard1" in names
        assert "guard2" in names
        assert "guard3" in names

    def test_names_empty_when_no_guards(self):
        """Names returns empty list when no guards registered."""
        # Arrange
        guards = FSMGuards()

        # Act & Assert
        assert guards.names() == []

    def test_register_overwrites(self):
        """Registering same name replaces the function."""
        # Arrange
        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        eid = world.spawn()

        # Register first version
        guards.register("changeable", lambda w, e: True)
        assert guards.check("changeable", world, eid) is True

        # Act - overwrite with new function
        guards.register("changeable", lambda w, e: False)

        # Assert
        assert guards.check("changeable", world, eid) is False

    def test_guard_receives_correct_args(self):
        """Guard function gets (world, eid)."""
        # Arrange
        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        eid = world.spawn()

        # Track what arguments the guard received
        received_args = []

        def tracking_guard(w, e):
            received_args.append((w, e))
            return True

        guards.register("tracker", tracking_guard)

        # Act
        guards.check("tracker", world, eid)

        # Assert
        assert len(received_args) == 1
        assert received_args[0][0] is world
        assert received_args[0][1] == eid

    def test_multiple_guards(self):
        """Register several, each works independently."""
        # Arrange
        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        eid1 = world.spawn()
        eid2 = world.spawn()

        # Register multiple guards with different logic
        guards.register("check_eid_even", lambda w, e: e % 2 == 0)
        guards.register("check_eid_odd", lambda w, e: e % 2 == 1)
        guards.register("always_true", lambda w, e: True)

        # Act & Assert
        # Each guard evaluates independently
        if eid1 % 2 == 0:
            assert guards.check("check_eid_even", world, eid1) is True
            assert guards.check("check_eid_odd", world, eid1) is False
        else:
            assert guards.check("check_eid_even", world, eid1) is False
            assert guards.check("check_eid_odd", world, eid1) is True

        assert guards.check("always_true", world, eid1) is True
        assert guards.check("always_true", world, eid2) is True

    def test_guard_can_inspect_world(self):
        """Guard can query world state for decision."""
        # Arrange
        from dataclasses import dataclass

        @dataclass
        class Health:
            value: int

        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        world.register_component(Health)

        eid1 = world.spawn()
        world.attach(eid1, Health(value=50))

        eid2 = world.spawn()
        world.attach(eid2, Health(value=100))

        # Guard checks health component
        def low_health(w, e):
            if w.has(e, Health):
                return w.get(e, Health).value < 75
            return False

        guards.register("low_health", low_health)

        # Act & Assert
        assert guards.check("low_health", world, eid1) is True  # 50 < 75
        assert guards.check("low_health", world, eid2) is False  # 100 >= 75

    def test_guards_can_return_truthy_falsy_values(self):
        """Guards work with any truthy/falsy return value."""
        # Arrange
        guards = FSMGuards()
        engine = Engine(tps=20, seed=42)
        world = engine.world
        eid = world.spawn()

        guards.register("returns_int", lambda w, e: 42)
        guards.register("returns_zero", lambda w, e: 0)
        guards.register("returns_string", lambda w, e: "hello")
        guards.register("returns_empty_string", lambda w, e: "")
        guards.register("returns_none", lambda w, e: None)

        # Act & Assert - Python's truthiness rules apply
        assert guards.check("returns_int", world, eid)  # 42 is truthy
        assert not guards.check("returns_zero", world, eid)  # 0 is falsy
        assert guards.check("returns_string", world, eid)  # non-empty string is truthy
        assert not guards.check("returns_empty_string", world, eid)  # empty string is falsy
        assert not guards.check("returns_none", world, eid)  # None is falsy
