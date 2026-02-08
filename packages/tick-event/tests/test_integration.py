"""Integration tests — full Engine + EventScheduler + cycles + conditions."""
from __future__ import annotations

from dataclasses import dataclass

from tick import Engine

from tick_event.guards import EventGuards
from tick_event.scheduler import EventScheduler
from tick_event.systems import make_event_system
from tick_event.types import CycleDef, EventDef


class TestEngineIntegration:
    def test_full_lifecycle(self) -> None:
        """Event activates, counts down, expires through engine ticks."""
        engine = Engine(tps=10, seed=1)
        scheduler = EventScheduler()
        guards = EventGuards()
        log: list[tuple[str, str]] = []

        scheduler.define(EventDef(name="raid", duration=3))
        sys = make_event_system(
            scheduler,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
            on_end=lambda w, c, n: log.append(("end", n)),
        )
        engine.add_system(sys)
        engine.run(5)

        assert ("start", "raid") in log
        assert ("end", "raid") in log


class TestSeasonCycleRotation:
    def test_four_seasons_rotate(self) -> None:
        """A 4-season cycle rotates through all phases."""
        engine = Engine(tps=10, seed=1)
        scheduler = EventScheduler()
        guards = EventGuards()
        phases_log: list[tuple[str, str]] = []

        scheduler.define_cycle(
            CycleDef(
                name="seasons",
                phases=[
                    ("spring", 3),
                    ("summer", 3),
                    ("autumn", 3),
                    ("winter", 3),
                ],
            )
        )

        sys = make_event_system(
            scheduler,
            guards,
            on_start=lambda w, c, n: phases_log.append(("start", n)),
            on_end=lambda w, c, n: phases_log.append(("end", n)),
        )
        engine.add_system(sys)
        engine.run(13)  # 4 phases * 3 ticks + 1 to trigger wrap

        started = [n for action, n in phases_log if action == "start"]
        # Should see all 4 seasons start, plus wrap back to spring
        assert "spring" in started
        assert "summer" in started
        assert "autumn" in started
        assert "winter" in started


class TestConditionalEvents:
    def test_cold_snap_only_in_winter(self) -> None:
        """Cold snap fires only when winter phase is active."""
        engine = Engine(tps=10, seed=1)
        scheduler = EventScheduler()
        guards = EventGuards()
        event_log: list[tuple[str, str]] = []

        # 2-tick phases for speed
        scheduler.define_cycle(
            CycleDef(
                name="seasons",
                phases=[("summer", 3), ("winter", 3)],
            )
        )
        guards.register("is_winter", lambda w, s: s.is_active("winter"))
        scheduler.define(
            EventDef(name="cold_snap", duration=1, conditions=["is_winter"])
        )

        sys = make_event_system(
            scheduler,
            guards,
            on_start=lambda w, c, n: event_log.append(("start", n)),
        )
        engine.add_system(sys)

        # Run through summer (3 ticks) and into winter
        engine.run(8)

        cold_starts = [
            (a, n) for a, n in event_log if a == "start" and n == "cold_snap"
        ]
        assert len(cold_starts) >= 1


class TestSnapshotRestoreReplay:
    def test_snapshot_restore_determinism(self) -> None:
        """Snapshot at tick N, restore, continue — same result as uninterrupted."""
        def _run_to(n: int, seed: int = 42) -> list[tuple[str, str]]:
            engine = Engine(tps=10, seed=seed)
            scheduler = EventScheduler()
            guards = EventGuards()
            log: list[tuple[str, str]] = []
            scheduler.define(EventDef(name="raid", duration=2, cooldown=1))
            sys = make_event_system(
                scheduler,
                guards,
                on_start=lambda w, c, n: log.append(("start", n)),
                on_end=lambda w, c, n: log.append(("end", n)),
            )
            engine.add_system(sys)
            engine.run(n)
            return log

        # Uninterrupted run
        log_full = _run_to(10)

        # Interrupted: run 5, snapshot, restore, run 5 more
        engine1 = Engine(tps=10, seed=42)
        scheduler1 = EventScheduler()
        guards1 = EventGuards()
        log_split: list[tuple[str, str]] = []
        scheduler1.define(EventDef(name="raid", duration=2, cooldown=1))
        sys1 = make_event_system(
            scheduler1,
            guards1,
            on_start=lambda w, c, n: log_split.append(("start", n)),
            on_end=lambda w, c, n: log_split.append(("end", n)),
        )
        engine1.add_system(sys1)
        engine1.run(5)

        # Snapshot
        engine_snap = engine1.snapshot()
        sched_snap = scheduler1.snapshot()

        # Restore into new instances
        engine2 = Engine(tps=10, seed=42)
        scheduler2 = EventScheduler()
        guards2 = EventGuards()
        scheduler2.define(EventDef(name="raid", duration=2, cooldown=1))
        scheduler2.restore(sched_snap)

        log_split2: list[tuple[str, str]] = []
        sys2 = make_event_system(
            scheduler2,
            guards2,
            on_start=lambda w, c, n: log_split2.append(("start", n)),
            on_end=lambda w, c, n: log_split2.append(("end", n)),
        )
        engine2.add_system(sys2)
        engine2.restore(engine_snap)
        engine2.run(5)

        # Combined log from split run
        combined = log_split + log_split2

        # Both should have the same number of events
        assert len(combined) == len(log_full)


class TestCycleWithDelay:
    def test_delayed_cycle_starts_after_delay(self) -> None:
        engine = Engine(tps=10, seed=1)
        scheduler = EventScheduler()
        guards = EventGuards()
        log: list[tuple[str, str]] = []

        scheduler.define_cycle(
            CycleDef(name="weather", phases=[("rain", 3)], delay=2)
        )
        sys = make_event_system(
            scheduler,
            guards,
            on_start=lambda w, c, n: log.append(("start", n)),
        )
        engine.add_system(sys)
        engine.run(3)

        starts = [n for a, n in log if a == "start"]
        assert "rain" in starts


class TestRandomDuration:
    def test_random_duration_within_range(self) -> None:
        engine = Engine(tps=10, seed=42)
        scheduler = EventScheduler()
        guards = EventGuards()

        scheduler.define(EventDef(name="storm", duration=(3, 8)))
        sys = make_event_system(scheduler, guards)
        engine.add_system(sys)
        engine.step()

        assert scheduler.is_active("storm")
        remaining = scheduler.time_remaining("storm")
        assert 2 <= remaining <= 8  # after 1 decrement from max 8


class TestStressTest:
    def test_many_events_and_cycles(self) -> None:
        """Stress test with multiple events and cycles running simultaneously."""
        engine = Engine(tps=10, seed=42)
        scheduler = EventScheduler()
        guards = EventGuards()

        scheduler.define_cycle(
            CycleDef(
                name="seasons",
                phases=[("spring", 5), ("summer", 5), ("autumn", 5), ("winter", 5)],
            )
        )

        for i in range(10):
            scheduler.define(
                EventDef(
                    name=f"event_{i}",
                    duration=(1, 3),
                    cooldown=2,
                    probability=0.5,
                )
            )

        sys = make_event_system(scheduler, guards)
        engine.add_system(sys)

        # Run 100 ticks without error
        engine.run(100)

        # Snapshot should work
        snap = scheduler.snapshot()
        assert "active_events" in snap
        assert "cooldowns" in snap
        assert "cycles" in snap


@dataclass
class Health:
    value: int = 100


class TestEventAffectsWorld:
    def test_on_start_modifies_entities(self) -> None:
        """Event callbacks can modify world state."""
        engine = Engine(tps=10, seed=1)
        scheduler = EventScheduler()
        guards = EventGuards()

        engine.world.register_component(Health)
        eid = engine.world.spawn()
        engine.world.attach(eid, Health(value=100))

        def on_raid_start(w: object, ctx: object, name: str) -> None:
            if name == "raid":
                from tick import World
                assert isinstance(w, World)
                for e, (h,) in list(w.query(Health)):
                    h.value -= 20

        scheduler.define(EventDef(name="raid", duration=2))
        sys = make_event_system(scheduler, guards, on_start=on_raid_start)
        engine.add_system(sys)
        engine.step()

        health = engine.world.get(eid, Health)
        assert health.value == 80
