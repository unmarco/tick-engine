"""Tests for tick_colony.events module - narrative log."""

import pytest
from tick_colony import EventLog, Event


class TestEventLog:
    def test_eventlog_creation(self):
        log = EventLog()
        assert len(log) == 0

    def test_eventlog_creation_with_max_entries(self):
        log = EventLog(max_entries=100)
        assert len(log) == 0

    def test_emit_event(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=42, name="goblin")
        assert len(log) == 1

    def test_emit_multiple_events(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)
        log.emit(tick=2, type="move", entity_id=1, x=5, y=10)
        log.emit(tick=3, type="attack", attacker=1, target=2)
        assert len(log) == 3

    def test_query_all_events(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)
        log.emit(tick=2, type="move", entity_id=1)
        log.emit(tick=3, type="attack", entity_id=1)

        events = log.query()
        assert len(events) == 3
        assert all(isinstance(e, Event) for e in events)

    def test_query_with_type_filter(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)
        log.emit(tick=2, type="move", entity_id=1)
        log.emit(tick=3, type="spawn", entity_id=2)
        log.emit(tick=4, type="move", entity_id=2)

        spawn_events = log.query(type="spawn")
        assert len(spawn_events) == 2
        assert all(e.type == "spawn" for e in spawn_events)

    def test_query_with_after_filter(self):
        log = EventLog()
        log.emit(tick=1, type="event", data_val=1)
        log.emit(tick=5, type="event", data_val=5)
        log.emit(tick=10, type="event", data_val=10)
        log.emit(tick=15, type="event", data_val=15)

        events = log.query(after=5)
        assert len(events) == 2
        assert events[0].tick == 10
        assert events[1].tick == 15

    def test_query_with_before_filter(self):
        log = EventLog()
        log.emit(tick=1, type="event", data_val=1)
        log.emit(tick=5, type="event", data_val=5)
        log.emit(tick=10, type="event", data_val=10)
        log.emit(tick=15, type="event", data_val=15)

        events = log.query(before=10)
        assert len(events) == 2
        assert events[0].tick == 1
        assert events[1].tick == 5

    def test_query_with_multiple_filters(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)
        log.emit(tick=5, type="move", entity_id=1)
        log.emit(tick=10, type="spawn", entity_id=2)
        log.emit(tick=15, type="move", entity_id=2)
        log.emit(tick=20, type="spawn", entity_id=3)

        events = log.query(type="spawn", after=5, before=20)
        assert len(events) == 1
        assert events[0].tick == 10
        assert events[0].type == "spawn"

    def test_last_returns_most_recent(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)
        log.emit(tick=5, type="spawn", entity_id=2)
        log.emit(tick=10, type="move", entity_id=1)

        last_spawn = log.last("spawn")
        assert last_spawn is not None
        assert last_spawn.tick == 5
        assert last_spawn.data["entity_id"] == 2

    def test_last_returns_none_if_not_found(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)

        last_attack = log.last("attack")
        assert last_attack is None

    def test_last_with_empty_log(self):
        log = EventLog()
        assert log.last("anything") is None

    def test_ring_buffer_behavior_unlimited(self):
        log = EventLog(max_entries=0)  # Unlimited
        for i in range(1000):
            log.emit(tick=i, type="event", value=i)
        assert len(log) == 1000

    def test_ring_buffer_behavior_limited(self):
        log = EventLog(max_entries=5)
        for i in range(10):
            log.emit(tick=i, type="event", value=i)

        assert len(log) == 5
        events = log.query()
        # Should have most recent 5 events (ticks 5-9)
        assert events[0].tick == 5
        assert events[-1].tick == 9

    def test_snapshot_produces_list(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=1)
        log.emit(tick=2, type="move", x=5, y=10)

        snapshot = log.snapshot()
        assert isinstance(snapshot, list)
        assert len(snapshot) == 2

    def test_snapshot_contains_dicts(self):
        log = EventLog()
        log.emit(tick=1, type="spawn", entity_id=42)

        snapshot = log.snapshot()
        assert isinstance(snapshot[0], dict)
        assert snapshot[0]["tick"] == 1
        assert snapshot[0]["type"] == "spawn"
        assert snapshot[0]["data"]["entity_id"] == 42

    def test_restore_from_snapshot(self):
        log1 = EventLog()
        log1.emit(tick=1, type="spawn", entity_id=1)
        log1.emit(tick=2, type="move", x=5, y=10)

        snapshot = log1.snapshot()

        log2 = EventLog()
        log2.restore(snapshot)

        assert len(log2) == 2
        events = log2.query()
        assert events[0].tick == 1
        assert events[0].type == "spawn"
        assert events[1].tick == 2
        assert events[1].type == "move"

    def test_restore_clears_existing_events(self):
        log = EventLog()
        log.emit(tick=1, type="original", value=1)
        log.emit(tick=2, type="original", value=2)

        new_snapshot = [
            {"tick": 10, "type": "new", "data": {"value": 10}},
        ]

        log.restore(new_snapshot)

        assert len(log) == 1
        events = log.query()
        assert events[0].tick == 10
        assert events[0].type == "new"

    def test_snapshot_restore_roundtrip(self):
        log1 = EventLog()
        log1.emit(tick=1, type="spawn", entity_id=1, name="goblin")
        log1.emit(tick=5, type="attack", attacker=1, target=2, damage=10)
        log1.emit(tick=10, type="move", entity_id=1, x=5, y=7)

        snapshot = log1.snapshot()

        log2 = EventLog()
        log2.restore(snapshot)

        assert len(log2) == len(log1)

        events1 = log1.query()
        events2 = log2.query()

        for e1, e2 in zip(events1, events2):
            assert e1.tick == e2.tick
            assert e1.type == e2.type
            assert e1.data == e2.data

    def test_event_data_contains_kwargs(self):
        log = EventLog()
        log.emit(tick=1, type="custom", foo="bar", num=42, flag=True)

        events = log.query()
        assert events[0].data["foo"] == "bar"
        assert events[0].data["num"] == 42
        assert events[0].data["flag"] is True

    def test_len_returns_event_count(self):
        log = EventLog()
        assert len(log) == 0

        log.emit(tick=1, type="e1")
        assert len(log) == 1

        log.emit(tick=2, type="e2")
        log.emit(tick=3, type="e3")
        assert len(log) == 3
