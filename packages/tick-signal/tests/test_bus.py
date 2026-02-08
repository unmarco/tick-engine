"""Unit tests for SignalBus."""
from __future__ import annotations

from tick_signal import SignalBus


def test_subscribe_and_flush():
    """Subscribe handler, publish signal, flush dispatches to handler."""
    bus = SignalBus()
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("test_signal", handler)
    bus.publish("test_signal", value=42)
    bus.flush()

    assert len(received) == 1
    assert received[0] == ("test_signal", {"value": 42})


def test_publish_without_subscribe():
    """Publish signal with no subscribers, flush is a no-op (no error)."""
    bus = SignalBus()
    bus.publish("no_subscribers", value=123)
    bus.flush()  # Should not raise


def test_multiple_handlers():
    """Multiple handlers for same signal, all called in registration order."""
    bus = SignalBus()
    received_a = []
    received_b = []
    received_c = []

    def handler_a(signal_name: str, data: dict) -> None:
        received_a.append((signal_name, data))

    def handler_b(signal_name: str, data: dict) -> None:
        received_b.append((signal_name, data))

    def handler_c(signal_name: str, data: dict) -> None:
        received_c.append((signal_name, data))

    # Subscribe in specific order
    bus.subscribe("event", handler_a)
    bus.subscribe("event", handler_b)
    bus.subscribe("event", handler_c)

    bus.publish("event", msg="hello")
    bus.flush()

    # All handlers should receive the signal
    assert len(received_a) == 1
    assert len(received_b) == 1
    assert len(received_c) == 1
    assert received_a[0] == ("event", {"msg": "hello"})
    assert received_b[0] == ("event", {"msg": "hello"})
    assert received_c[0] == ("event", {"msg": "hello"})


def test_multiple_signals():
    """Different signal names route to different handlers."""
    bus = SignalBus()
    received_alpha = []
    received_beta = []

    def handler_alpha(signal_name: str, data: dict) -> None:
        received_alpha.append((signal_name, data))

    def handler_beta(signal_name: str, data: dict) -> None:
        received_beta.append((signal_name, data))

    bus.subscribe("alpha", handler_alpha)
    bus.subscribe("beta", handler_beta)

    bus.publish("alpha", x=1)
    bus.publish("beta", y=2)
    bus.flush()

    assert len(received_alpha) == 1
    assert len(received_beta) == 1
    assert received_alpha[0] == ("alpha", {"x": 1})
    assert received_beta[0] == ("beta", {"y": 2})


def test_fifo_ordering():
    """Publish A then B, handlers called in A-then-B order."""
    bus = SignalBus()
    order = []

    def handler(signal_name: str, data: dict) -> None:
        order.append(signal_name)

    bus.subscribe("signal_a", handler)
    bus.subscribe("signal_b", handler)

    bus.publish("signal_a", value=1)
    bus.publish("signal_b", value=2)
    bus.flush()

    assert order == ["signal_a", "signal_b"]


def test_data_passing():
    """Publish with keyword data, handler receives {"key": "value"} dict."""
    bus = SignalBus()
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append(data)

    bus.subscribe("data_test", handler)
    bus.publish("data_test", name="Alice", age=30, active=True)
    bus.flush()

    assert len(received) == 1
    assert received[0] == {"name": "Alice", "age": 30, "active": True}


def test_empty_data():
    """Publish with no kwargs, handler receives empty dict."""
    bus = SignalBus()
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append(data)

    bus.subscribe("empty_test", handler)
    bus.publish("empty_test")
    bus.flush()

    assert len(received) == 1
    assert received[0] == {}


def test_flush_clears_queue():
    """After flush, queue is empty — second flush dispatches nothing."""
    bus = SignalBus()
    call_count = 0

    def handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe("test", handler)
    bus.publish("test", value=1)
    bus.flush()

    assert call_count == 1

    # Second flush without new publish should not call handler
    bus.flush()
    assert call_count == 1


def test_clear_without_dispatch():
    """Clear removes queued signals, subsequent flush dispatches nothing."""
    bus = SignalBus()
    call_count = 0

    def handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe("test", handler)
    bus.publish("test", value=1)
    bus.clear()
    bus.flush()

    assert call_count == 0


def test_unsubscribe():
    """Unsubscribe handler, publish+flush does not call it."""
    bus = SignalBus()
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("test", handler)
    bus.unsubscribe("test", handler)
    bus.publish("test", value=42)
    bus.flush()

    assert len(received) == 0


def test_unsubscribe_noop():
    """Unsubscribe handler that isn't subscribed — no error."""
    bus = SignalBus()

    def handler(signal_name: str, data: dict) -> None:
        pass

    # Should not raise
    bus.unsubscribe("nonexistent", handler)
    bus.unsubscribe("test", handler)


def test_unsubscribe_one_of_many():
    """Unsubscribe one handler, others still receive signals."""
    bus = SignalBus()
    received_a = []
    received_b = []
    received_c = []

    def handler_a(signal_name: str, data: dict) -> None:
        received_a.append((signal_name, data))

    def handler_b(signal_name: str, data: dict) -> None:
        received_b.append((signal_name, data))

    def handler_c(signal_name: str, data: dict) -> None:
        received_c.append((signal_name, data))

    bus.subscribe("event", handler_a)
    bus.subscribe("event", handler_b)
    bus.subscribe("event", handler_c)

    # Unsubscribe handler_b
    bus.unsubscribe("event", handler_b)

    bus.publish("event", msg="test")
    bus.flush()

    assert len(received_a) == 1
    assert len(received_b) == 0  # Should not receive
    assert len(received_c) == 1


def test_signals_during_flush_deferred():
    """Handler publishes new signal during flush — deferred to next flush."""
    bus = SignalBus()
    received = []

    def handler_initial(signal_name: str, data: dict) -> None:
        received.append(("initial", signal_name, data))
        # Publish new signal during flush
        bus.publish("deferred", nested=True)

    def handler_deferred(signal_name: str, data: dict) -> None:
        received.append(("deferred", signal_name, data))

    bus.subscribe("initial", handler_initial)
    bus.subscribe("deferred", handler_deferred)

    bus.publish("initial", value=1)
    bus.flush()

    # First flush: only initial handler called
    assert len(received) == 1
    assert received[0] == ("initial", "initial", {"value": 1})

    # Second flush: deferred signal dispatched
    bus.flush()
    assert len(received) == 2
    assert received[1] == ("deferred", "deferred", {"nested": True})


def test_no_subscribers_for_signal():
    """Publishing a signal no one subscribes to doesn't error."""
    bus = SignalBus()

    def handler(signal_name: str, data: dict) -> None:
        pass

    bus.subscribe("subscribed", handler)

    # Publish to unsubscribed signal
    bus.publish("unsubscribed", value=1)
    bus.flush()  # Should not raise


def test_multiple_publishes_same_signal():
    """Publish same signal twice, handler called twice."""
    bus = SignalBus()
    call_count = 0
    received = []

    def handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1
        received.append(data)

    bus.subscribe("repeated", handler)
    bus.publish("repeated", count=1)
    bus.publish("repeated", count=2)
    bus.flush()

    assert call_count == 2
    assert received == [{"count": 1}, {"count": 2}]


def test_handler_registration_order():
    """Verify handlers are called in exact registration order."""
    bus = SignalBus()
    order = []

    def handler_1(signal_name: str, data: dict) -> None:
        order.append(1)

    def handler_2(signal_name: str, data: dict) -> None:
        order.append(2)

    def handler_3(signal_name: str, data: dict) -> None:
        order.append(3)

    bus.subscribe("event", handler_1)
    bus.subscribe("event", handler_2)
    bus.subscribe("event", handler_3)

    bus.publish("event")
    bus.flush()

    assert order == [1, 2, 3]


def test_multiple_signals_multiple_handlers():
    """Complex scenario: multiple signals, multiple handlers, mixed subscriptions."""
    bus = SignalBus()
    received_a = []
    received_b = []

    def handler_a(signal_name: str, data: dict) -> None:
        received_a.append((signal_name, data))

    def handler_b(signal_name: str, data: dict) -> None:
        received_b.append((signal_name, data))

    # handler_a subscribes to both signals
    bus.subscribe("signal_x", handler_a)
    bus.subscribe("signal_y", handler_a)

    # handler_b only subscribes to signal_y
    bus.subscribe("signal_y", handler_b)

    bus.publish("signal_x", x=1)
    bus.publish("signal_y", y=2)
    bus.flush()

    # handler_a should receive both
    assert len(received_a) == 2
    assert received_a[0] == ("signal_x", {"x": 1})
    assert received_a[1] == ("signal_y", {"y": 2})

    # handler_b should only receive signal_y
    assert len(received_b) == 1
    assert received_b[0] == ("signal_y", {"y": 2})


def test_clear_preserves_subscriptions():
    """Clear only removes queued signals, subscriptions remain."""
    bus = SignalBus()
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("test", handler)
    bus.publish("test", value=1)
    bus.clear()

    # Publish after clear
    bus.publish("test", value=2)
    bus.flush()

    # Should only receive the second publish
    assert len(received) == 1
    assert received[0] == ("test", {"value": 2})


def test_flush_with_empty_queue():
    """Flush with empty queue is a no-op."""
    bus = SignalBus()
    call_count = 0

    def handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe("test", handler)
    bus.flush()  # No signals published

    assert call_count == 0


def test_resubscribe_same_handler():
    """Subscribing same handler twice results in handler being called twice."""
    bus = SignalBus()
    call_count = 0

    def handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe("test", handler)
    bus.subscribe("test", handler)  # Subscribe again

    bus.publish("test")
    bus.flush()

    assert call_count == 2


def test_unsubscribe_after_resubscribe():
    """Unsubscribe removes only one instance of multiply-subscribed handler."""
    bus = SignalBus()
    call_count = 0

    def handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1

    bus.subscribe("test", handler)
    bus.subscribe("test", handler)
    bus.unsubscribe("test", handler)  # Remove one instance

    bus.publish("test")
    bus.flush()

    assert call_count == 1
