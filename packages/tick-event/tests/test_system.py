"""Tests for tick_event.systems — make_event_system factory."""
from __future__ import annotations

from tick import Engine, TickContext, World

from tick_event.guards import EventGuards
from tick_event.scheduler import EventScheduler
from tick_event.systems import make_event_system
from tick_event.types import EventDef


def _setup(
    seed: int = 42,
) -> tuple[Engine, EventScheduler, EventGuards, list[tuple[str, str]]]:
    """Create engine, scheduler, guards, and a log list."""
    engine = Engine(tps=10, seed=seed)
    scheduler = EventScheduler()
    guards = EventGuards()
    log: list[tuple[str, str]] = []
    return engine, scheduler, guards, log


class TestActivation:
    def test_event_activates_immediately(self) -> None:
        engine, scheduler, guards, log = _setup()
        scheduler.define(EventDef(name="raid", duration=3))
        sys = make_event_system(
            scheduler, guards, on_start=lambda w, c, n: log.append(("start", n))
        )
        engine.add_system(sys)
        engine.step()
        assert scheduler.is_active("raid")
        assert ("start", "raid") in log

    def test_event_with_probability_zero_never_fires(self) -> None:
        engine, scheduler, guards, log = _setup()
        scheduler.define(EventDef(name="rare", duration=5, probability=0.0))
        sys = make_event_system(scheduler, guards)
        engine.add_system(sys)
        engine.run(10)
        assert not scheduler.is_active("rare")

    def test_event_with_probability_one_always_fires(self) -> None:
        engine, scheduler, guards, log = _setup()
        scheduler.define(EventDef(name="sure", duration=5, probability=1.0))
        sys = make_event_system(scheduler, guards)
        engine.add_system(sys)
        engine.step()
        assert scheduler.is_active("sure")


class TestCountdown:
    def test_event_expires_after_duration(self) -> None:
        engine, scheduler, guards, log = _setup()
        # Use a cooldown to prevent immediate re-activation after expiry
        scheduler.define(EventDef(name="raid", duration=3, cooldown=10))
        sys = make_event_system(
            scheduler,
            guards,
            on_end=lambda w, c, n: log.append(("end", n)),
        )
        engine.add_system(sys)
        # tick 1: activate (rem=3), tick 2: rem=2, tick 3: rem=1, tick 4: rem=0 → end
        engine.run(4)
        assert not scheduler.is_active("raid")
        assert ("end", "raid") in log

    def test_on_tick_called_while_active(self) -> None:
        engine, scheduler, guards, log = _setup()
        tick_log: list[tuple[str, int]] = []
        scheduler.define(EventDef(name="raid", duration=3))
        sys = make_event_system(
            scheduler,
            guards,
            on_tick=lambda w, c, n, r: tick_log.append((n, r)),
        )
        engine.add_system(sys)
        engine.run(4)
        # on_tick fires for ticks where event is still active after decrement
        raid_ticks = [(n, r) for n, r in tick_log if n == "raid"]
        assert len(raid_ticks) >= 1


class TestCooldown:
    def test_cooldown_prevents_refire(self) -> None:
        engine, scheduler, guards, log = _setup()
        # duration=2, cooldown=5 → fires tick 1, expires tick 3, cooldown blocks through tick 7
        scheduler.define(EventDef(name="raid", duration=2, cooldown=5))
        sys = make_event_system(
            scheduler, guards, on_start=lambda w, c, n: log.append(("start", n))
        )
        engine.add_system(sys)
        engine.run(6)
        start_count = sum(1 for action, name in log if action == "start" and name == "raid")
        assert start_count == 1  # cooldown still active, only fired once

    def test_cooldown_expires_and_refires(self) -> None:
        engine, scheduler, guards, log = _setup()
        scheduler.define(EventDef(name="raid", duration=1, cooldown=3))
        sys = make_event_system(
            scheduler, guards, on_start=lambda w, c, n: log.append(("start", n))
        )
        engine.add_system(sys)
        # tick 1: activate (rem=1)
        # tick 2: expire, cooldown=3, expired-skip. Step 4: cd→2
        # tick 3: cd→1
        # tick 4: cd→0 (removed). Step 5: re-activate
        engine.run(5)
        start_count = sum(1 for action, name in log if action == "start" and name == "raid")
        assert start_count == 2


class TestProbability:
    def test_deterministic_probability(self) -> None:
        """Same seed produces same activation pattern."""
        results: list[list[bool]] = []
        for _ in range(2):
            engine, scheduler, guards, _ = _setup(seed=99)
            scheduler.define(EventDef(name="maybe", duration=1, probability=0.5))
            sys = make_event_system(scheduler, guards)
            engine.add_system(sys)
            run_results: list[bool] = []
            for _ in range(20):
                engine.step()
                run_results.append(scheduler.is_active("maybe"))
            results.append(run_results)
        assert results[0] == results[1]


class TestConditions:
    def test_condition_blocks_activation(self) -> None:
        engine, scheduler, guards, log = _setup()
        guards.register("is_winter", lambda w, s: False)
        scheduler.define(
            EventDef(name="cold_snap", duration=5, conditions=["is_winter"])
        )
        sys = make_event_system(scheduler, guards)
        engine.add_system(sys)
        engine.run(5)
        assert not scheduler.is_active("cold_snap")

    def test_condition_allows_activation(self) -> None:
        engine, scheduler, guards, log = _setup()
        guards.register("is_winter", lambda w, s: True)
        scheduler.define(
            EventDef(name="cold_snap", duration=5, conditions=["is_winter"])
        )
        sys = make_event_system(scheduler, guards)
        engine.add_system(sys)
        engine.step()
        assert scheduler.is_active("cold_snap")


class TestDefinitionOrder:
    def test_events_evaluated_in_definition_order(self) -> None:
        engine, scheduler, guards, log = _setup()
        scheduler.define(EventDef(name="first", duration=100))
        scheduler.define(EventDef(name="second", duration=100))
        scheduler.define(EventDef(name="third", duration=100))
        sys = make_event_system(
            scheduler, guards, on_start=lambda w, c, n: log.append(("start", n))
        )
        engine.add_system(sys)
        engine.step()
        starts = [n for action, n in log if action == "start"]
        assert starts == ["first", "second", "third"]
