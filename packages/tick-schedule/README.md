# tick-schedule

Countdown timers and periodic triggers for the tick engine. One-shot timers auto-detach after firing. Periodic triggers repeat indefinitely.

## Install

```bash
pip install tick-schedule
```

```python
from tick_schedule import Timer, Periodic, make_timer_system, make_periodic_system
```

## Quick Example

```python
from tick import Engine, World
from tick.types import TickContext
from tick_schedule import Timer, Periodic, make_timer_system, make_periodic_system

engine = Engine(tps=10)

# One-shot timer: fires after 3 ticks, then auto-detaches
def on_timer(world: World, ctx: TickContext, eid: int, timer: Timer) -> None:
    print(f"[tick {ctx.tick_number}] timer '{timer.name}' fired for entity {eid}")

bomb = engine.world.spawn()
engine.world.attach(bomb, Timer(name="explode", remaining=3))
engine.add_system(make_timer_system(on_fire=on_timer))

# Periodic trigger: fires every 5 ticks, stays attached
def on_periodic(world: World, ctx: TickContext, eid: int, periodic: Periodic) -> None:
    print(f"[tick {ctx.tick_number}] periodic '{periodic.name}' triggered")

beacon = engine.world.spawn()
engine.world.attach(beacon, Periodic(name="ping", interval=5))
engine.add_system(make_periodic_system(on_fire=on_periodic))

engine.run(10)
```

## API Reference

### Components

**`Timer(name: str, remaining: int)`** -- One-shot countdown. Decrements `remaining` each tick. Fires and auto-detaches when it reaches zero.

**`Periodic(name: str, interval: int, elapsed: int = 0)`** -- Repeating trigger. Increments `elapsed` each tick, fires when `elapsed >= interval`, then resets `elapsed` to zero.

### System Factories

**`make_timer_system(on_fire)`** -- Returns a system that processes all `Timer` components. The callback signature is `(world, ctx, entity_id, timer) -> None`. The timer is detached before the callback fires, enabling chaining (attach a new timer in the callback).

**`make_periodic_system(on_fire)`** -- Returns a system that processes all `Periodic` components. Same callback signature as timers.

## Part of [tick-engine](../../README.md)

MIT License
