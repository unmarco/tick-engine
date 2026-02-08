"""Integration tests for SignalBus with colony EventLog."""

import pytest
from tick_colony import SignalBus, EventLog


class TestSignalIntegration:
    """Test SignalBus→EventLog bridge, publish/flush/subscribe."""

    def test_basic_publish_and_flush(self):
        """Publish signal, flush, verify handler called."""
        bus = SignalBus()

        # Track calls
        calls = []

        def handler(signal_name, data):
            calls.append((signal_name, data))

        # Subscribe
        bus.subscribe("test_signal", handler)

        # Publish
        bus.publish("test_signal", entity_id=42, value=100)

        # Verify not called yet
        assert len(calls) == 0

        # Flush
        bus.flush()

        # Verify handler called
        assert len(calls) == 1
        assert calls[0][0] == "test_signal"
        assert calls[0][1] == {"entity_id": 42, "value": 100}

    def test_signal_to_eventlog_bridge(self):
        """Subscribe handler that emits to EventLog."""
        bus = SignalBus()
        event_log = EventLog()

        # Bridge handler — extract tick, pass rest as data kwargs
        def bridge_handler(signal_name, data):
            tick = data.get("tick", 0)
            rest = {k: v for k, v in data.items() if k != "tick"}
            event_log.emit(tick=tick, type=signal_name, **rest)

        # Subscribe
        bus.subscribe("forage_complete", bridge_handler)

        # Publish signal
        bus.publish("forage_complete", tick=10, entity_id=5, amount=25)

        # Flush
        bus.flush()

        # Query EventLog
        events = event_log.query(type="forage_complete")
        assert len(events) == 1
        assert events[0].tick == 10
        assert events[0].type == "forage_complete"
        assert events[0].data["entity_id"] == 5
        assert events[0].data["amount"] == 25

    def test_multiple_signals_to_eventlog(self):
        """Publish multiple signal types, flush once, all recorded in EventLog."""
        bus = SignalBus()
        event_log = EventLog()

        # Bridge handler
        def bridge_handler(signal_name, data):
            tick = data.get("tick", 0)
            rest = {k: v for k, v in data.items() if k != "tick"}
            event_log.emit(tick=tick, type=signal_name, **rest)

        # Subscribe multiple signal types
        bus.subscribe("forage_done", bridge_handler)
        bus.subscribe("rest_done", bridge_handler)
        bus.subscribe("death", bridge_handler)

        # Publish 3 different signals
        bus.publish("forage_done", tick=5, entity_id=1, amount=10)
        bus.publish("rest_done", tick=7, entity_id=2, restored=50)
        bus.publish("death", tick=10, entity_id=3, cause="starvation")

        # Flush once
        bus.flush()

        # Verify all 3 recorded
        assert len(event_log) == 3

        forage_events = event_log.query(type="forage_done")
        assert len(forage_events) == 1
        assert forage_events[0].data["entity_id"] == 1

        rest_events = event_log.query(type="rest_done")
        assert len(rest_events) == 1
        assert rest_events[0].data["entity_id"] == 2

        death_events = event_log.query(type="death")
        assert len(death_events) == 1
        assert death_events[0].data["cause"] == "starvation"

    def test_flush_clears_queue(self):
        """Flush clears queue, subsequent publish/flush records separately."""
        bus = SignalBus()
        event_log = EventLog()

        # Bridge handler
        def bridge_handler(signal_name, data):
            tick = data.get("tick", 0)
            rest = {k: v for k, v in data.items() if k != "tick"}
            event_log.emit(tick=tick, type=signal_name, **rest)

        # Subscribe
        bus.subscribe("action_complete", bridge_handler)

        # First batch
        bus.publish("action_complete", tick=1, entity_id=10)
        bus.flush()

        # Verify first event
        assert len(event_log) == 1

        # Second batch
        bus.publish("action_complete", tick=2, entity_id=20)
        bus.flush()

        # Verify second event (not duplicated)
        assert len(event_log) == 2

        events = event_log.query(type="action_complete")
        assert len(events) == 2
        assert events[0].data["entity_id"] == 10
        assert events[1].data["entity_id"] == 20

    def test_multiple_subscribers_same_signal(self):
        """Two handlers subscribed to same signal, both called on flush."""
        bus = SignalBus()

        # Track calls for each handler
        calls_a = []
        calls_b = []

        def handler_a(signal_name, data):
            calls_a.append((signal_name, data))

        def handler_b(signal_name, data):
            calls_b.append((signal_name, data))

        # Subscribe both to "death"
        bus.subscribe("death", handler_a)
        bus.subscribe("death", handler_b)

        # Publish once
        bus.publish("death", entity_id=99, cause="old_age")

        # Flush
        bus.flush()

        # Verify both handlers called
        assert len(calls_a) == 1
        assert len(calls_b) == 1
        assert calls_a[0][1]["entity_id"] == 99
        assert calls_b[0][1]["cause"] == "old_age"

    def test_unsubscribe(self):
        """Unsubscribe handler, then publish/flush does not call handler."""
        bus = SignalBus()

        # Track calls
        calls = []

        def handler(signal_name, data):
            calls.append((signal_name, data))

        # Subscribe
        bus.subscribe("test_signal", handler)

        # Publish and flush (should call)
        bus.publish("test_signal", value=1)
        bus.flush()
        assert len(calls) == 1

        # Unsubscribe
        bus.unsubscribe("test_signal", handler)

        # Publish and flush again (should NOT call)
        bus.publish("test_signal", value=2)
        bus.flush()
        assert len(calls) == 1  # Still 1, not incremented
