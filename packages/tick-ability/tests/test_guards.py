"""Tests for tick_ability.guards — AbilityGuards registry."""
from __future__ import annotations

import pytest

from tick import Engine

from tick_ability.guards import AbilityGuards
from tick_ability.manager import AbilityManager


class TestAbilityGuards:
    def test_register_and_check(self) -> None:
        guards = AbilityGuards()
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)

        guards.register("always_true", lambda w, m: True)
        result = guards.check("always_true", engine.world, manager)
        assert result is True

    def test_overwrite_guard(self) -> None:
        guards = AbilityGuards()
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)

        guards.register("test", lambda w, m: True)
        guards.register("test", lambda w, m: False)  # overwrite

        result = guards.check("test", engine.world, manager)
        assert result is False

    def test_unknown_guard_raises_key_error(self) -> None:
        guards = AbilityGuards()
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)

        with pytest.raises(KeyError):
            guards.check("unknown", engine.world, manager)

    def test_has_correctness(self) -> None:
        guards = AbilityGuards()
        guards.register("test", lambda w, m: True)

        assert guards.has("test")
        assert not guards.has("unknown")

    def test_names_lists_all(self) -> None:
        guards = AbilityGuards()
        guards.register("first", lambda w, m: True)
        guards.register("second", lambda w, m: False)
        guards.register("third", lambda w, m: True)

        names = guards.names()
        assert set(names) == {"first", "second", "third"}
        assert len(names) == 3

    def test_guard_receives_correct_arguments(self) -> None:
        guards = AbilityGuards()
        manager = AbilityManager()
        engine = Engine(tps=10, seed=42)

        received_world = None
        received_manager = None

        def capture_args(w, m):
            nonlocal received_world, received_manager
            received_world = w
            received_manager = m
            return True

        guards.register("capture", capture_args)
        guards.check("capture", engine.world, manager)

        assert received_world is engine.world
        assert received_manager is manager
