"""Tests for tick_event.guards — EventGuards registry."""
from __future__ import annotations

import pytest
from tick import Engine

from tick_event.guards import EventGuards
from tick_event.scheduler import EventScheduler


def _make_world() -> Engine:
    return Engine(tps=10)


class TestRegister:
    def test_register_and_check(self) -> None:
        guards = EventGuards()
        guards.register("always", lambda w, s: True)
        engine = _make_world()
        scheduler = EventScheduler()
        assert guards.check("always", engine.world, scheduler) is True

    def test_register_false_guard(self) -> None:
        guards = EventGuards()
        guards.register("never", lambda w, s: False)
        engine = _make_world()
        scheduler = EventScheduler()
        assert guards.check("never", engine.world, scheduler) is False

    def test_overwrite(self) -> None:
        guards = EventGuards()
        guards.register("flip", lambda w, s: True)
        guards.register("flip", lambda w, s: False)
        engine = _make_world()
        scheduler = EventScheduler()
        assert guards.check("flip", engine.world, scheduler) is False


class TestCheckErrors:
    def test_unregistered_raises_key_error(self) -> None:
        guards = EventGuards()
        engine = _make_world()
        scheduler = EventScheduler()
        with pytest.raises(KeyError):
            guards.check("missing", engine.world, scheduler)


class TestInspection:
    def test_has_registered(self) -> None:
        guards = EventGuards()
        guards.register("exists", lambda w, s: True)
        assert guards.has("exists") is True
        assert guards.has("nope") is False

    def test_names_empty(self) -> None:
        guards = EventGuards()
        assert guards.names() == []

    def test_names_returns_all(self) -> None:
        guards = EventGuards()
        guards.register("a", lambda w, s: True)
        guards.register("b", lambda w, s: False)
        assert sorted(guards.names()) == ["a", "b"]


class TestWorldAndSchedulerAccess:
    def test_guard_inspects_world(self) -> None:
        guards = EventGuards()
        engine = _make_world()
        scheduler = EventScheduler()
        eid = engine.world.spawn()
        guards.register("has_entities", lambda w, s: len(w.entities()) > 0)
        assert guards.check("has_entities", engine.world, scheduler) is True
        engine.world.despawn(eid)
        assert guards.check("has_entities", engine.world, scheduler) is False

    def test_guard_inspects_scheduler(self) -> None:
        guards = EventGuards()
        engine = _make_world()
        scheduler = EventScheduler()
        guards.register("winter_active", lambda w, s: s.is_active("winter"))
        assert guards.check("winter_active", engine.world, scheduler) is False
        scheduler._activate("winter", 10, 1)
        assert guards.check("winter_active", engine.world, scheduler) is True

    def test_guard_inspects_both(self) -> None:
        guards = EventGuards()
        engine = _make_world()
        scheduler = EventScheduler()
        engine.world.spawn()
        scheduler._activate("summer", 5, 1)
        guards.register(
            "entities_in_summer",
            lambda w, s: len(w.entities()) > 0 and s.is_active("summer"),
        )
        assert (
            guards.check("entities_in_summer", engine.world, scheduler) is True
        )
