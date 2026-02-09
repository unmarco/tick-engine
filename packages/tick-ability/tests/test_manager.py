"""Tests for tick_ability.manager — AbilityManager."""
from __future__ import annotations

from random import Random

import pytest

from tick import Engine, TickContext

from tick_ability.guards import AbilityGuards
from tick_ability.manager import AbilityManager
from tick_ability.types import AbilityDef, AbilityState


class TestRegistration:
    def test_define_registers_ability_and_initializes_state(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="fireball", duration=5, max_charges=3))

        defn = manager.definition("fireball")
        assert defn is not None
        assert defn.name == "fireball"

        state = manager.state("fireball")
        assert state is not None
        assert state.charges == 3

    def test_define_with_unlimited_charges(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="unlimited", duration=5, max_charges=-1))

        state = manager.state("unlimited")
        assert state is not None
        assert state.charges == 0  # unlimited means charges not tracked

    def test_define_preserves_insertion_order(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="first", duration=1))
        manager.define(AbilityDef(name="second", duration=2))
        manager.define(AbilityDef(name="third", duration=3))

        names = manager.defined_abilities()
        assert names == ["first", "second", "third"]

    def test_definition_returns_none_for_unknown(self) -> None:
        manager = AbilityManager()
        result = manager.definition("unknown")
        assert result is None

    def test_redefine_preserves_runtime_state(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5, max_charges=3))

        # Modify state
        state = manager.state("test")
        assert state is not None
        state.charges = 1
        state.cooldown_remaining = 5

        # Re-define
        manager.define(AbilityDef(name="test", duration=10, max_charges=5))

        # State should be preserved
        state = manager.state("test")
        assert state is not None
        assert state.charges == 1  # preserved
        assert state.cooldown_remaining == 5  # preserved


class TestInvocation:
    def test_invoke_succeeds_and_consumes_charge(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5, max_charges=2))

        # Create a context
        ctx = TickContext(
            tick_number=1,
            dt=0.1,
            elapsed=0.1,
            request_stop=lambda: None,
            random=Random(42),
        )

        result = manager.invoke("test", engine.world, ctx)
        assert result is True

        state = manager.state("test")
        assert state is not None
        assert state.charges == 1  # consumed
        assert state.active_remaining == 5
        assert state.active_started_at == 1

    def test_invoke_fails_when_not_defined(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("unknown", engine.world, ctx)
        assert result is False

    def test_invoke_fails_when_active(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5))

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        # First invoke succeeds
        result1 = manager.invoke("test", engine.world, ctx)
        assert result1 is True

        # Second invoke fails (still active)
        result2 = manager.invoke("test", engine.world, ctx)
        assert result2 is False

    def test_invoke_fails_when_on_cooldown(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5))

        # Manually set cooldown
        state = manager.state("test")
        assert state is not None
        state.cooldown_remaining = 10

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("test", engine.world, ctx)
        assert result is False

    def test_invoke_fails_when_no_charges(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5, max_charges=2))

        # Set charges to 0
        state = manager.state("test")
        assert state is not None
        state.charges = 0

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("test", engine.world, ctx)
        assert result is False

    def test_invoke_fails_when_guard_blocks(self) -> None:
        manager = AbilityManager()
        guards = AbilityGuards()
        engine = Engine(tps=10, seed=42)

        guards.register("always_false", lambda w, m: False)
        manager.define(
            AbilityDef(name="test", duration=5, conditions=["always_false"])
        )

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("test", engine.world, ctx, guards=guards)
        assert result is False

    def test_invoke_with_unlimited_charges_does_not_decrement(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5, max_charges=-1))

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("test", engine.world, ctx)
        assert result is True

        state = manager.state("test")
        assert state is not None
        assert state.charges == 0  # stays 0 for unlimited

    def test_invoke_starts_regen_timer(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(
            AbilityDef(name="test", duration=5, max_charges=3, charge_regen=10)
        )

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("test", engine.world, ctx)
        assert result is True

        state = manager.state("test")
        assert state is not None
        assert state.charges == 2
        assert state.regen_remaining == 10  # started

    def test_invoke_does_not_restart_regen_if_already_running(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(
            AbilityDef(name="test", duration=5, max_charges=3, charge_regen=10)
        )

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        # First invoke: starts regen
        manager.invoke("test", engine.world, ctx)
        state = manager.state("test")
        assert state is not None
        assert state.regen_remaining == 10

        # Manually decrement regen
        state.regen_remaining = 5

        # Reset active so we can invoke again
        state.active_remaining = 0
        state.active_started_at = -1

        # Second invoke: should NOT restart regen (already running)
        manager.invoke("test", engine.world, ctx)
        state = manager.state("test")
        assert state is not None
        assert state.regen_remaining == 5  # preserved, not reset to 10

    def test_invoke_with_random_duration_is_deterministic(self) -> None:
        results: list[int] = []
        for _ in range(2):
            manager = AbilityManager()
            engine = Engine(tps=10, seed=99)
            manager.define(AbilityDef(name="test", duration=(3, 10)))

            ctx = TickContext(
                tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(99)
            )

            manager.invoke("test", engine.world, ctx)
            state = manager.state("test")
            assert state is not None
            results.append(state.active_remaining)

        assert results[0] == results[1]  # same seed produces same duration

    def test_invoke_sets_active_started_at(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5))

        ctx = TickContext(
            tick_number=42, dt=0.1, elapsed=4.2, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("test", engine.world, ctx)
        assert result is True

        state = manager.state("test")
        assert state is not None
        assert state.active_started_at == 42

    def test_invoke_instantaneous_ability(self) -> None:
        """Instantaneous abilities (duration=0) set active_started_at but active_remaining=0."""
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="instant", duration=0))

        ctx = TickContext(
            tick_number=5, dt=0.1, elapsed=0.5, request_stop=lambda: None, random=Random(42)
        )

        result = manager.invoke("instant", engine.world, ctx)
        assert result is True

        state = manager.state("instant")
        assert state is not None
        assert state.active_remaining == 0
        assert state.active_started_at == 5

    def test_invoke_instantaneous_blocks_reinvocation_before_processing(self) -> None:
        """Cannot re-invoke an instantaneous ability before the system processes it."""
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="instant", duration=0, max_charges=3))

        ctx = TickContext(
            tick_number=1, dt=0.1, elapsed=0.1, request_stop=lambda: None, random=Random(42)
        )

        result1 = manager.invoke("instant", engine.world, ctx)
        assert result1 is True

        # Second invoke should fail — active_started_at != -1
        result2 = manager.invoke("instant", engine.world, ctx)
        assert result2 is False


class TestQueries:
    def test_is_available_checks_all_conditions(self) -> None:
        manager = AbilityManager()
        guards = AbilityGuards()
        engine = Engine(tps=10, seed=42)

        guards.register("has_mana", lambda w, m: True)
        manager.define(
            AbilityDef(name="test", duration=5, conditions=["has_mana"])
        )

        result = manager.is_available("test", engine.world, guards=guards)
        assert result is True

    def test_is_available_false_when_active(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5))

        # Set as active
        state = manager.state("test")
        assert state is not None
        state.active_remaining = 3

        result = manager.is_available("test", engine.world)
        assert result is False

    def test_is_available_false_when_on_cooldown(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5))

        # Set cooldown
        state = manager.state("test")
        assert state is not None
        state.cooldown_remaining = 10

        result = manager.is_available("test", engine.world)
        assert result is False

    def test_is_available_false_when_no_charges(self) -> None:
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)
        manager.define(AbilityDef(name="test", duration=5, max_charges=2))

        # Set charges to 0
        state = manager.state("test")
        assert state is not None
        state.charges = 0

        result = manager.is_available("test", engine.world)
        assert result is False

    def test_is_available_false_when_guard_fails(self) -> None:
        manager = AbilityManager()
        guards = AbilityGuards()
        engine = Engine(tps=10, seed=42)

        guards.register("always_false", lambda w, m: False)
        manager.define(
            AbilityDef(name="test", duration=5, conditions=["always_false"])
        )

        result = manager.is_available("test", engine.world, guards=guards)
        assert result is False

    def test_is_active_correctness(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5))

        assert not manager.is_active("test")

        state = manager.state("test")
        assert state is not None
        state.active_remaining = 3

        assert manager.is_active("test")

    def test_charges_returns_current_count(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5, max_charges=3))

        assert manager.charges("test") == 3

        state = manager.state("test")
        assert state is not None
        state.charges = 1

        assert manager.charges("test") == 1

    def test_charges_returns_minus_one_for_unlimited(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5, max_charges=-1))

        assert manager.charges("test") == -1

    def test_charges_raises_key_error_for_unknown(self) -> None:
        manager = AbilityManager()
        with pytest.raises(KeyError):
            manager.charges("unknown")

    def test_time_remaining_correctness(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5))

        assert manager.time_remaining("test") == 0

        state = manager.state("test")
        assert state is not None
        state.active_remaining = 7

        assert manager.time_remaining("test") == 7

    def test_time_remaining_raises_key_error_for_unknown(self) -> None:
        manager = AbilityManager()
        with pytest.raises(KeyError):
            manager.time_remaining("unknown")

    def test_cooldown_remaining_correctness(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5))

        assert manager.cooldown_remaining("test") == 0

        state = manager.state("test")
        assert state is not None
        state.cooldown_remaining = 10

        assert manager.cooldown_remaining("test") == 10

    def test_cooldown_remaining_raises_key_error_for_unknown(self) -> None:
        manager = AbilityManager()
        with pytest.raises(KeyError):
            manager.cooldown_remaining("unknown")

    def test_state_returns_ability_state_or_none(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5))

        state = manager.state("test")
        assert state is not None
        assert isinstance(state, AbilityState)

        unknown_state = manager.state("unknown")
        assert unknown_state is None

    def test_defined_abilities_returns_names_in_order(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="alpha", duration=1))
        manager.define(AbilityDef(name="beta", duration=2))
        manager.define(AbilityDef(name="gamma", duration=3))

        names = manager.defined_abilities()
        assert names == ["alpha", "beta", "gamma"]


class TestSerialization:
    def test_snapshot_restore_round_trip(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="fireball", duration=5, max_charges=2))
        manager.define(AbilityDef(name="shield", duration=10, max_charges=3))

        # Modify state
        state1 = manager.state("fireball")
        assert state1 is not None
        state1.charges = 1
        state1.cooldown_remaining = 5
        state1.active_remaining = 3
        state1.active_started_at = 42
        state1.regen_remaining = 7

        # Snapshot
        snapshot = manager.snapshot()

        # Create new manager and restore
        manager2 = AbilityManager()
        manager2.define(AbilityDef(name="fireball", duration=5, max_charges=2))
        manager2.define(AbilityDef(name="shield", duration=10, max_charges=3))
        manager2.restore(snapshot)

        # Verify state
        restored = manager2.state("fireball")
        assert restored is not None
        assert restored.charges == 1
        assert restored.cooldown_remaining == 5
        assert restored.active_remaining == 3
        assert restored.active_started_at == 42
        assert restored.regen_remaining == 7

    def test_restore_clears_previous_state(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="test", duration=5))

        # Set some state
        state = manager.state("test")
        assert state is not None
        state.charges = 99
        state.cooldown_remaining = 88

        # Restore with empty snapshot
        manager.restore({"abilities": []})

        # State should be cleared (since "test" not in snapshot)
        restored = manager.state("test")
        assert restored is None

    def test_restore_skips_unknown_ability_names(self) -> None:
        manager = AbilityManager()
        manager.define(AbilityDef(name="known", duration=5))

        snapshot = {
            "abilities": [
                {
                    "name": "known",
                    "charges": 1,
                    "cooldown_remaining": 0,
                    "active_remaining": 0,
                    "active_started_at": -1,
                    "regen_remaining": 0,
                },
                {
                    "name": "unknown",
                    "charges": 5,
                    "cooldown_remaining": 10,
                    "active_remaining": 3,
                    "active_started_at": 50,
                    "regen_remaining": 2,
                },
            ]
        }

        # Should not raise, just skip "unknown"
        manager.restore(snapshot)

        known_state = manager.state("known")
        assert known_state is not None
        assert known_state.charges == 1

        unknown_state = manager.state("unknown")
        assert unknown_state is None
