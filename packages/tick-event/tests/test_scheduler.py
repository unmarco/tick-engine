"""Tests for tick_event.scheduler — EventScheduler."""
from __future__ import annotations

import random

from tick_event.scheduler import EventScheduler
from tick_event.types import ActiveEvent, CycleDef, CycleState, EventDef


class TestDefine:
    def test_define_event(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="raid", duration=10))
        assert s.definition("raid") is not None

    def test_definition_order_preserved(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="b", duration=1))
        s.define(EventDef(name="a", duration=1))
        s.define(EventDef(name="c", duration=1))
        assert s._definition_order == ["b", "a", "c"]

    def test_redefine_keeps_order(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="x", duration=1))
        s.define(EventDef(name="y", duration=2))
        s.define(EventDef(name="x", duration=99))
        assert s._definition_order == ["x", "y"]
        assert s.definition("x") is not None
        assert s.definition("x").duration == 99  # type: ignore[union-attr]

    def test_definition_not_found(self) -> None:
        s = EventScheduler()
        assert s.definition("nope") is None


class TestCycles:
    def test_define_cycle_no_delay(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="seasons", phases=[("spring", 5), ("summer", 5)]))
        state = s._cycle_states["seasons"]
        assert state.phase_index == 0
        assert state.delay_remaining == 0

    def test_define_cycle_with_delay(self) -> None:
        s = EventScheduler()
        s.define_cycle(
            CycleDef(name="seasons", phases=[("spring", 5)], delay=3)
        )
        state = s._cycle_states["seasons"]
        assert state.phase_index == -1
        assert state.delay_remaining == 3

    def test_is_active_cycle_phase(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="seasons", phases=[("spring", 5), ("summer", 5)]))
        # phase_index=0 means spring is current, but delay_remaining=0
        # After define_cycle with no delay, we need to set up the remaining
        s._cycle_states["seasons"].delay_remaining = 5
        assert s.is_active("spring") is True
        assert s.is_active("summer") is False


class TestQueries:
    def test_is_active_event(self) -> None:
        s = EventScheduler()
        assert s.is_active("raid") is False
        s._activate("raid", 10, 1)
        assert s.is_active("raid") is True

    def test_active_events(self) -> None:
        s = EventScheduler()
        s._activate("raid", 10, 1)
        s._activate("famine", 5, 2)
        events = s.active_events()
        names = {e.name for e in events}
        assert names == {"raid", "famine"}

    def test_time_remaining_event(self) -> None:
        s = EventScheduler()
        assert s.time_remaining("raid") == 0
        s._activate("raid", 7, 1)
        assert s.time_remaining("raid") == 7

    def test_time_remaining_cycle_phase(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="seasons", phases=[("spring", 10), ("summer", 5)]))
        s._cycle_states["seasons"].delay_remaining = 8
        assert s.time_remaining("spring") == 8


class TestActivateDeactivate:
    def test_activate(self) -> None:
        s = EventScheduler()
        s._activate("raid", 10, 42)
        ae = s._active["raid"]
        assert ae.remaining == 10
        assert ae.started_at == 42

    def test_deactivate_with_cooldown(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="raid", duration=5, cooldown=3))
        s._activate("raid", 5, 1)
        s._deactivate("raid")
        assert "raid" not in s._active
        assert s._cooldowns["raid"] == 3

    def test_deactivate_without_cooldown(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="raid", duration=5))
        s._activate("raid", 5, 1)
        s._deactivate("raid")
        assert "raid" not in s._active
        assert "raid" not in s._cooldowns


class TestCooldowns:
    def test_decrement_cooldowns(self) -> None:
        s = EventScheduler()
        s._cooldowns["raid"] = 3
        s._decrement_cooldowns()
        assert s._cooldowns["raid"] == 2
        s._decrement_cooldowns()
        assert s._cooldowns["raid"] == 1
        s._decrement_cooldowns()
        assert "raid" not in s._cooldowns

    def test_is_on_cooldown(self) -> None:
        s = EventScheduler()
        assert s._is_on_cooldown("raid") is False
        s._cooldowns["raid"] = 2
        assert s._is_on_cooldown("raid") is True


class TestResolveDuration:
    def test_fixed(self) -> None:
        s = EventScheduler()
        defn = EventDef(name="raid", duration=10)
        rng = random.Random(42)
        assert s._resolve_duration(defn, rng) == 10

    def test_random_range(self) -> None:
        s = EventScheduler()
        defn = EventDef(name="raid", duration=(5, 15))
        rng = random.Random(42)
        result = s._resolve_duration(defn, rng)
        assert 5 <= result <= 15


class TestAdvanceCycle:
    def test_delay_countdown(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="c", phases=[("a", 3)], delay=2))
        ended, started = s._advance_cycle("c", 1)
        assert ended is None and started is None
        assert s._cycle_states["c"].delay_remaining == 1

    def test_delay_to_first_phase(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="c", phases=[("a", 3)], delay=1))
        ended, started = s._advance_cycle("c", 1)
        assert ended is None
        assert started == "a"
        assert s._cycle_states["c"].phase_index == 0
        assert s._cycle_states["c"].delay_remaining == 3

    def test_phase_transition(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="c", phases=[("a", 2), ("b", 3)]))
        s._cycle_states["c"].delay_remaining = 1  # 1 tick remaining in "a"
        ended, started = s._advance_cycle("c", 5)
        assert ended == "a"
        assert started == "b"
        assert s._cycle_states["c"].phase_index == 1
        assert s._cycle_states["c"].delay_remaining == 3

    def test_phase_wraps_around(self) -> None:
        s = EventScheduler()
        s.define_cycle(CycleDef(name="c", phases=[("a", 2), ("b", 1)]))
        # Set to last phase with 1 remaining
        s._cycle_states["c"].phase_index = 1
        s._cycle_states["c"].delay_remaining = 1
        ended, started = s._advance_cycle("c", 10)
        assert ended == "b"
        assert started == "a"
        assert s._cycle_states["c"].phase_index == 0


class TestSnapshot:
    def test_round_trip(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="raid", duration=5, cooldown=3))
        s.define_cycle(CycleDef(name="seasons", phases=[("spring", 10), ("summer", 10)]))
        s._activate("raid", 4, 1)
        s._cooldowns["famine"] = 2
        s._cycle_states["seasons"].phase_index = 1
        s._cycle_states["seasons"].delay_remaining = 7

        data = s.snapshot()

        s2 = EventScheduler()
        s2.define(EventDef(name="raid", duration=5, cooldown=3))
        s2.define_cycle(CycleDef(name="seasons", phases=[("spring", 10), ("summer", 10)]))
        s2.restore(data)

        assert s2.is_active("raid")
        assert s2._active["raid"].remaining == 4
        assert s2._cooldowns["famine"] == 2
        assert s2._cycle_states["seasons"].phase_index == 1
        assert s2._cycle_states["seasons"].delay_remaining == 7

    def test_restore_clears_previous_state(self) -> None:
        s = EventScheduler()
        s.define(EventDef(name="raid", duration=5))
        s._activate("raid", 5, 1)
        s._cooldowns["old"] = 10

        s.restore({"active_events": [], "cooldowns": {}, "cycles": []})
        assert not s.is_active("raid")
        assert not s._is_on_cooldown("old")
