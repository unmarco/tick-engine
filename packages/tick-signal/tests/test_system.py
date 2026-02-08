"""Integration tests for signal system with tick engine."""
from __future__ import annotations

from dataclasses import dataclass

from tick_signal import SignalBus, make_signal_system
from tick import Engine


def test_system_flushes_bus():
    """Create engine, add signal system, publish signal, run 1 tick — handler called."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("test_event", handler)

    # Create system that publishes signal
    def publisher_system(world, ctx) -> None:
        bus.publish("test_event", tick=ctx.tick_number)

    # Add systems: publisher first, then signal system
    engine.add_system(publisher_system)
    engine.add_system(make_signal_system(bus))

    engine.run(1)

    assert len(received) == 1
    assert received[0] == ("test_event", {"tick": 1})


def test_multi_tick():
    """Publish in tick 1 system, signal system flushes — handler gets signal; tick 2 no new publish — handler not called again."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("tick_event", handler)

    publish_on_tick_1 = True

    def conditional_publisher(world, ctx) -> None:
        nonlocal publish_on_tick_1
        if publish_on_tick_1 and ctx.tick_number == 1:
            bus.publish("tick_event", tick=ctx.tick_number)
            publish_on_tick_1 = False

    engine.add_system(conditional_publisher)
    engine.add_system(make_signal_system(bus))

    # Tick 1: signal published and flushed
    engine.run(1)
    assert len(received) == 1
    assert received[0] == ("tick_event", {"tick": 1})

    # Tick 2: no new publish, handler not called again
    engine.run(1)
    assert len(received) == 1  # Still just 1


def test_system_ordering():
    """System A publishes signal, signal system registered after A — flush picks up signal from same tick."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("ordering_test", handler)

    def system_a(world, ctx) -> None:
        bus.publish("ordering_test", source="system_a", tick=ctx.tick_number)

    # Add system_a first, then signal system
    engine.add_system(system_a)
    engine.add_system(make_signal_system(bus))

    engine.run(1)

    # Signal published by system_a should be flushed in same tick
    assert len(received) == 1
    assert received[0] == ("ordering_test", {"source": "system_a", "tick": 1})


def test_deferred_signals_across_ticks():
    """Handler publishes new signal during flush — deferred signal dispatched on next tick."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler_initial(signal_name: str, data: dict) -> None:
        received.append(("initial", signal_name, data))
        # Publish new signal during flush
        bus.publish("deferred", nested=True)

    def handler_deferred(signal_name: str, data: dict) -> None:
        received.append(("deferred", signal_name, data))

    bus.subscribe("initial", handler_initial)
    bus.subscribe("deferred", handler_deferred)

    def publisher_system(world, ctx) -> None:
        if ctx.tick_number == 1:
            bus.publish("initial", tick=ctx.tick_number)

    engine.add_system(publisher_system)
    engine.add_system(make_signal_system(bus))

    # Tick 1: initial signal published and flushed, deferred signal queued
    engine.run(1)
    assert len(received) == 1
    assert received[0] == ("initial", "initial", {"tick": 1})

    # Tick 2: deferred signal flushed
    engine.run(1)
    assert len(received) == 2
    assert received[1] == ("deferred", "deferred", {"nested": True})


def test_multiple_systems_publish():
    """Multiple systems publish different signals in same tick, all flushed."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("event_a", handler)
    bus.subscribe("event_b", handler)
    bus.subscribe("event_c", handler)

    def system_a(world, ctx) -> None:
        bus.publish("event_a", source="a")

    def system_b(world, ctx) -> None:
        bus.publish("event_b", source="b")

    def system_c(world, ctx) -> None:
        bus.publish("event_c", source="c")

    engine.add_system(system_a)
    engine.add_system(system_b)
    engine.add_system(system_c)
    engine.add_system(make_signal_system(bus))

    engine.run(1)

    assert len(received) == 3
    assert received[0] == ("event_a", {"source": "a"})
    assert received[1] == ("event_b", {"source": "b"})
    assert received[2] == ("event_c", {"source": "c"})


def test_signal_system_with_world_entities():
    """Integration test: systems interact with world entities and publish signals."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    @dataclass
    class Counter:
        value: int

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("counter_updated", handler)

    # Setup: create entity with counter
    entity = engine.world.spawn()
    engine.world.attach(entity, Counter(value=0))

    def increment_system(world, ctx) -> None:
        for eid, (counter,) in world.query(Counter):
            counter.value += 1
            bus.publish("counter_updated", entity=eid, value=counter.value, tick=ctx.tick_number)

    engine.add_system(increment_system)
    engine.add_system(make_signal_system(bus))

    engine.run(3)

    assert len(received) == 3
    assert received[0] == ("counter_updated", {"entity": entity, "value": 1, "tick": 1})
    assert received[1] == ("counter_updated", {"entity": entity, "value": 2, "tick": 2})
    assert received[2] == ("counter_updated", {"entity": entity, "value": 3, "tick": 3})


def test_signal_before_signal_system_same_tick():
    """Signal published before signal system in execution order is flushed in same tick."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append(data.get("tick"))

    bus.subscribe("early_signal", handler)

    def early_publisher(world, ctx) -> None:
        bus.publish("early_signal", tick=ctx.tick_number)

    # Early publisher runs before signal system
    engine.add_system(early_publisher)
    engine.add_system(make_signal_system(bus))

    engine.run(2)

    # Both ticks should flush their signals
    assert received == [1, 2]


def test_signal_after_signal_system_deferred():
    """Signal published after signal system in execution order is deferred to next tick."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append(data.get("tick"))

    bus.subscribe("late_signal", handler)

    def late_publisher(world, ctx) -> None:
        bus.publish("late_signal", tick=ctx.tick_number)

    # Signal system runs before late publisher
    engine.add_system(make_signal_system(bus))
    engine.add_system(late_publisher)

    engine.run(3)

    # First tick publishes but doesn't flush (signal system ran first)
    # Tick 2 flushes tick 1's signal, publishes tick 2
    # Tick 3 flushes tick 2's signal, publishes tick 3
    # After tick 3, tick 3's signal is still queued
    assert received == [1, 2]


def test_no_signal_system_no_flush():
    """Without signal system, signals are queued but never flushed."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("never_flushed", handler)

    def publisher_system(world, ctx) -> None:
        bus.publish("never_flushed", tick=ctx.tick_number)

    # Only add publisher, no signal system
    engine.add_system(publisher_system)

    engine.run(5)

    # No signals should be flushed
    assert len(received) == 0


def test_manual_flush_outside_tick():
    """Manual flush outside tick loop dispatches queued signals."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("manual_test", handler)

    def publisher_system(world, ctx) -> None:
        bus.publish("manual_test", tick=ctx.tick_number)

    # Only publisher, no signal system
    engine.add_system(publisher_system)

    engine.run(2)
    assert len(received) == 0  # No flush yet

    # Manual flush
    bus.flush()
    assert len(received) == 2
    assert received[0] == ("manual_test", {"tick": 1})
    assert received[1] == ("manual_test", {"tick": 2})


def test_clear_between_ticks():
    """Clearing bus between ticks discards queued signals."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("clearable", handler)

    def publisher_system(world, ctx) -> None:
        bus.publish("clearable", tick=ctx.tick_number)

    engine.add_system(publisher_system)
    # No signal system added

    engine.run(1)
    bus.clear()  # Clear queued signals
    engine.run(1)

    # Flush after clearing
    bus.flush()

    # Should only receive tick 2 signal (tick 1 was cleared)
    assert len(received) == 1
    assert received[0] == ("clearable", {"tick": 2})


def test_handler_modifies_world():
    """Signal handler can modify world state (via closure)."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)

    @dataclass
    class Flag:
        value: bool

    entity = engine.world.spawn()
    engine.world.attach(entity, Flag(value=False))

    def handler(signal_name: str, data: dict) -> None:
        # Modify world via closure
        flag = engine.world.get(entity, Flag)
        if flag:
            flag.value = True

    bus.subscribe("set_flag", handler)

    def publisher_system(world, ctx) -> None:
        bus.publish("set_flag")

    engine.add_system(publisher_system)
    engine.add_system(make_signal_system(bus))

    engine.run(1)

    flag = engine.world.get(entity, Flag)
    assert flag is not None
    assert flag.value is True


def test_multiple_signal_systems():
    """Multiple signal systems can be added (though unnecessary)."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append((signal_name, data))

    bus.subscribe("multi_flush", handler)

    def publisher_system(world, ctx) -> None:
        bus.publish("multi_flush", tick=ctx.tick_number)

    engine.add_system(publisher_system)
    engine.add_system(make_signal_system(bus))
    engine.add_system(make_signal_system(bus))  # Second flush (redundant)

    engine.run(1)

    # Signal flushed by first signal system, second flush does nothing
    assert len(received) == 1


def test_signal_with_tick_context_data():
    """Signals can carry tick context information."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def handler(signal_name: str, data: dict) -> None:
        received.append(data)

    bus.subscribe("context_test", handler)

    def publisher_system(world, ctx) -> None:
        bus.publish(
            "context_test",
            tick_number=ctx.tick_number,
            dt=ctx.dt,
            elapsed=ctx.elapsed,
        )

    engine.add_system(publisher_system)
    engine.add_system(make_signal_system(bus))

    engine.run(2)

    assert len(received) == 2
    assert received[0]["tick_number"] == 1
    assert received[0]["dt"] == 0.05
    assert received[0]["elapsed"] == 0.05
    assert received[1]["tick_number"] == 2
    assert received[1]["dt"] == 0.05
    assert received[1]["elapsed"] == 0.10


def test_unsubscribe_during_tick():
    """Handler can unsubscribe itself during processing."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    call_count = 0

    def self_unsubscribing_handler(signal_name: str, data: dict) -> None:
        nonlocal call_count
        call_count += 1
        # Unsubscribe after first call
        bus.unsubscribe("once", self_unsubscribing_handler)

    bus.subscribe("once", self_unsubscribing_handler)

    def publisher_system(world, ctx) -> None:
        bus.publish("once", tick=ctx.tick_number)

    engine.add_system(publisher_system)
    engine.add_system(make_signal_system(bus))

    engine.run(3)

    # Handler should only be called once (tick 1), then unsubscribed
    assert call_count == 1


def test_subscribe_during_tick():
    """New subscription during tick takes effect on next flush."""
    bus = SignalBus()
    engine = Engine(tps=20, seed=42)
    received = []

    def late_handler(signal_name: str, data: dict) -> None:
        received.append(("late", signal_name, data))

    subscribed = False

    def subscribing_system(world, ctx) -> None:
        nonlocal subscribed
        if ctx.tick_number == 1 and not subscribed:
            bus.subscribe("test_event", late_handler)
            subscribed = True
        bus.publish("test_event", tick=ctx.tick_number)

    engine.add_system(subscribing_system)
    engine.add_system(make_signal_system(bus))

    engine.run(2)

    # Tick 1: subscribe happens, signal published/flushed (late_handler gets it)
    # Tick 2: late_handler still subscribed
    assert len(received) == 2
