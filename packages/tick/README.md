# tick

A minimal, general-purpose tick engine in Python. Fixed-timestep loop, entity-component-system storage, seed-controlled RNG, and snapshot/restore for deterministic replay. Stdlib only.

## Install

```bash
pip install tick
```

```python
import tick
```

## Quick Example

```python
from dataclasses import dataclass
from tick import Engine, World
from tick.types import TickContext

@dataclass
class Counter:
    value: int = 0

def counting_system(world: World, ctx: TickContext) -> None:
    for eid, (c,) in world.query(Counter):
        c.value += 1
        print(f"tick {ctx.tick_number}: count={c.value}")

engine = Engine(tps=10)
e = engine.world.spawn()
engine.world.attach(e, Counter())
engine.add_system(counting_system)
engine.run(3)
```

## Core Concepts

- **Entity** -- an integer ID, nothing more.
- **Component** -- a plain dataclass. Data only, no behavior.
- **System** -- a callable `(World, TickContext) -> None`. Logic only, no state.
- **World** -- dict-of-dicts component storage with queries.
- **Clock** -- fixed timestep. `dt = 1 / tps`.
- **TickContext** -- frozen dataclass passed to every system each tick.

## API Reference

### Engine

```python
Engine(tps: int = 20, seed: int | None = None)
```

| Property / Method | Description |
|-------------------|-------------|
| `.world` | The `World` instance |
| `.clock` | The `Clock` instance |
| `.seed` | The RNG seed (auto-generated if not provided) |
| `.add_system(fn)` | Register a system |
| `.run(n)` | Run `n` ticks, calling on_start/on_stop hooks |
| `.step()` | Run a single tick (no lifecycle hooks) |
| `.run_forever()` | Run with real-time pacing until `ctx.request_stop()` |
| `.on_start(hook)` | Register a start lifecycle hook |
| `.on_stop(hook)` | Register a stop lifecycle hook |
| `.snapshot()` | Serialize engine state to a JSON-compatible dict |
| `.restore(data)` | Restore engine state from a snapshot dict |

### World

| Method | Description |
|--------|-------------|
| `.spawn() -> EntityId` | Create a new entity |
| `.despawn(eid)` | Remove entity and all its components |
| `.attach(eid, component)` | Attach a dataclass instance to an entity |
| `.detach(eid, ctype)` | Remove a component type from an entity |
| `.get(eid, ctype) -> T` | Get a component (raises `KeyError` or `DeadEntityError`) |
| `.has(eid, ctype) -> bool` | Check if entity has a component type |
| `.query(*ctypes)` | Yield `(eid, (comp, ...))` for entities with all given types |
| `.entities() -> frozenset` | All living entity IDs |
| `.alive(eid) -> bool` | Check if entity is alive |
| `.register_component(ctype)` | Register a type for snapshot/restore |

### TickContext

Frozen dataclass passed to every system:

| Field | Type | Description |
|-------|------|-------------|
| `tick_number` | `int` | Current tick (starts at 1) |
| `dt` | `float` | Seconds per tick (`1 / tps`) |
| `elapsed` | `float` | Total elapsed time |
| `request_stop` | `Callable` | Call to stop the engine |
| `random` | `random.Random` | Seed-controlled RNG instance |

### Exceptions

- **`DeadEntityError`** -- raised when accessing a despawned entity.
- **`SnapshotError`** -- raised on restore failures (version mismatch, unregistered type).

## Snapshot / Restore

```python
engine = Engine(tps=10, seed=42)
# ... set up systems, run ticks ...
data = engine.snapshot()  # JSON-serializable dict

engine2 = Engine(tps=10)
engine2.world.register_component(Counter)  # register before restore
engine2.restore(data)
```

Components must be flat dataclasses (no nested dataclasses). Call `register_component()` before restoring.

## Part of [tick-engine](../../README.md)

MIT License
