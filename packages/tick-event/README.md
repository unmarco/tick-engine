# tick-event

World-level event scheduling for the tick engine. Define probabilistic events with durations, cooldowns, guard conditions, and repeating phase cycles (e.g., seasons). Standalone manager + system factory pattern.

## Install

```bash
pip install tick-event
```

```python
from tick_event import EventDef, EventScheduler, EventGuards, make_event_system
```

## Quick Example

```python
from tick import Engine, World
from tick.types import TickContext
from tick_event import EventDef, CycleDef, EventScheduler, EventGuards, make_event_system

engine = Engine(tps=10, seed=42)
scheduler = EventScheduler()
guards = EventGuards()

# Define a probabilistic event
scheduler.define(EventDef(
    name="drought",
    duration=20,
    cooldown=50,
    probability=0.3,
))

# Define a repeating cycle (seasons)
scheduler.define_cycle(CycleDef(
    name="seasons",
    phases=[("spring", 100), ("summer", 100), ("autumn", 100), ("winter", 100)],
))

def on_start(world: World, ctx: TickContext, name: str) -> None:
    print(f"[tick {ctx.tick_number}] event started: {name}")

def on_end(world: World, ctx: TickContext, name: str) -> None:
    print(f"[tick {ctx.tick_number}] event ended: {name}")

engine.add_system(make_event_system(scheduler, guards, on_start=on_start, on_end=on_end))
engine.run(50)
```

## API Reference

### EventDef

```python
EventDef(
    name: str,
    duration: int | tuple[int, int],  # fixed ticks or (min, max) random range
    cooldown: int = 0,                 # min ticks before re-fire
    probability: float = 1.0,          # per-evaluation chance [0.0, 1.0]
    conditions: list[str] = [],        # guard names, ALL must pass
)
```

### CycleDef

```python
CycleDef(
    name: str,
    phases: list[tuple[str, int]],  # (phase_name, duration_ticks)
    delay: int = 0,                 # ticks before first phase
)
```

Repeating phase cycle. Phases loop indefinitely in order.

### EventScheduler

```python
scheduler = EventScheduler()
```

| Method | Description |
|--------|-------------|
| `.define(event_def)` | Register an event definition |
| `.define_cycle(cycle_def)` | Register a repeating cycle |
| `.is_active(name) -> bool` | Check if event or cycle phase is active |
| `.active_events() -> list[ActiveEvent]` | All currently active non-cycle events |
| `.time_remaining(name) -> int` | Remaining ticks (0 if inactive) |
| `.definition(name) -> EventDef or None` | Look up event definition |
| `.snapshot() -> dict` | Serialize runtime state |
| `.restore(data)` | Restore runtime state (re-register definitions first) |

### EventGuards

```python
guards = EventGuards()
guards.register("has_villagers", lambda world, scheduler: len(list(world.query(Villager))) > 0)
guards.check("has_villagers", world, scheduler)  # -> bool
```

Guard predicates receive `(world, scheduler)` and return `bool`.

### make_event_system

```python
make_event_system(
    scheduler: EventScheduler,
    guards: EventGuards,
    on_start=None,   # (world, ctx, event_name) -> None
    on_end=None,     # (world, ctx, event_name) -> None
    on_tick=None,    # (world, ctx, event_name, remaining) -> None
) -> System
```

Returns a system that evaluates events each tick. Tick order: decrement active events, tick active events, advance cycles, decrement cooldowns, evaluate inactive events.

## Part of [tick-engine](../../README.md)

MIT License
