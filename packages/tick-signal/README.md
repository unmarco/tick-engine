# tick-signal

In-process pub/sub event bus for the tick engine. Signals are queued on publish and dispatched FIFO on flush, giving you deterministic per-tick event processing.

## Install

```bash
pip install tick-signal
```

```python
from tick_signal import SignalBus, make_signal_system
```

## Quick Example

```python
from tick import Engine, World
from tick.types import TickContext
from tick_signal import SignalBus, make_signal_system

bus = SignalBus()

# Subscribe to signals
def on_damage(signal_name, data):
    print(f"received '{signal_name}': entity {data['eid']} took {data['amount']} damage")

bus.subscribe("damage", on_damage)

# Publish during a system -- dispatch happens later in the same tick
def combat_system(world: World, ctx: TickContext) -> None:
    bus.publish("damage", eid=0, amount=25)

engine = Engine(tps=10)
engine.add_system(combat_system)
engine.add_system(make_signal_system(bus))  # flushes the queue
engine.run(1)
# Output: received 'damage': entity 0 took 25 damage
```

## Dispatch Semantics

1. `publish()` queues the signal (does not call handlers immediately).
2. `flush()` dispatches all queued signals in FIFO order.
3. Signals published during flush are deferred to the next flush call.
4. `make_signal_system(bus)` returns a system that calls `flush()` once per tick.

This means ordering is predictable: systems that publish earlier in the tick have their signals dispatched when the signal system runs, all in a single batch.

## API Reference

### SignalBus

```python
bus = SignalBus()
```

| Method | Description |
|--------|-------------|
| `.subscribe(name, handler)` | Register a handler for a signal name |
| `.unsubscribe(name, handler)` | Remove a specific handler |
| `.publish(name, **data)` | Queue a signal with keyword data |
| `.flush()` | Dispatch all queued signals to their handlers |
| `.clear()` | Discard all queued signals without dispatching |

Handlers receive `(signal_name: str, data: dict)`.

### make_signal_system

```python
make_signal_system(bus: SignalBus) -> System
```

Returns a system that calls `bus.flush()` each tick. Add it after your other systems so all signals published during the tick get dispatched.

## Part of [tick-engine](../../README.md)

MIT License
