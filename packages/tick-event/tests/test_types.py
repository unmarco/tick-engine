"""Tests for tick_event.types — dataclass construction and defaults."""
from tick_event.types import ActiveEvent, CycleDef, CycleState, EventDef


class TestEventDef:
    def test_minimal(self) -> None:
        e = EventDef(name="famine", duration=10)
        assert e.name == "famine"
        assert e.duration == 10
        assert e.cooldown == 0
        assert e.probability == 1.0
        assert e.conditions == []

    def test_all_fields(self) -> None:
        e = EventDef(
            name="cold_snap",
            duration=(5, 15),
            cooldown=20,
            probability=0.3,
            conditions=["is_winter", "not_on_fire"],
        )
        assert e.duration == (5, 15)
        assert e.cooldown == 20
        assert e.probability == 0.3
        assert e.conditions == ["is_winter", "not_on_fire"]


class TestActiveEvent:
    def test_construction(self) -> None:
        ae = ActiveEvent(name="raid", remaining=5, started_at=100)
        assert ae.name == "raid"
        assert ae.remaining == 5
        assert ae.started_at == 100


class TestCycleDef:
    def test_minimal(self) -> None:
        c = CycleDef(name="seasons", phases=[("spring", 10), ("summer", 10)])
        assert c.name == "seasons"
        assert c.phases == [("spring", 10), ("summer", 10)]
        assert c.delay == 0

    def test_with_delay(self) -> None:
        c = CycleDef(name="seasons", phases=[("spring", 10)], delay=5)
        assert c.delay == 5


class TestCycleState:
    def test_construction(self) -> None:
        cs = CycleState(name="seasons", phase_index=2, delay_remaining=7)
        assert cs.name == "seasons"
        assert cs.phase_index == 2
        assert cs.delay_remaining == 7
