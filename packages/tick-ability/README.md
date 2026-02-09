# tick-ability

Player-triggered abilities for the tick engine. Charge-based abilities with cooldowns, durations, guard conditions, and charge regeneration. Standalone manager + system factory pattern.

## Install

```bash
pip install tick-ability
```

```python
from tick_ability import AbilityDef, AbilityManager, AbilityGuards, make_ability_system
```

## Quick Example

```python
from tick import Engine, World
from tick.types import TickContext
from tick_ability import AbilityDef, AbilityManager, AbilityGuards, make_ability_system

engine = Engine(tps=10, seed=42)
manager = AbilityManager()
guards = AbilityGuards()

# Define an ability: 5-tick effect, 10-tick cooldown, 2 charges
manager.define(AbilityDef(
    name="fireball",
    duration=5,
    cooldown=10,
    max_charges=2,
    charge_regen=20,
))

def on_start(world: World, ctx: TickContext, name: str) -> None:
    print(f"[tick {ctx.tick_number}] {name} activated!")

def on_end(world: World, ctx: TickContext, name: str) -> None:
    print(f"[tick {ctx.tick_number}] {name} expired")

engine.add_system(make_ability_system(manager, guards, on_start=on_start, on_end=on_end))

# Invoke between ticks (from UI, AI, network, etc.)
manager.invoke("fireball", engine.world, engine.clock.context(lambda: None, engine._rng))
engine.run(20)
```

## API Reference

### AbilityDef

```python
AbilityDef(
    name: str,
    duration: int | tuple[int, int],  # fixed ticks or (min, max) random range
    cooldown: int = 0,                 # ticks after effect ends before re-use
    max_charges: int = 1,              # -1 for unlimited
    charge_regen: int = 0,             # ticks between charge regeneration (0 = no regen)
    conditions: list[str] = [],        # guard names, ALL must pass
)
```

Duration of `0` creates an instantaneous ability (on_start + on_end fire on the same tick).

### AbilityManager

```python
manager = AbilityManager()
```

| Method | Description |
|--------|-------------|
| `.define(ability_def)` | Register an ability and initialize state |
| `.invoke(name, world, ctx, guards=None) -> bool` | Attempt to invoke; returns success |
| `.is_available(name, world, guards=None) -> bool` | Can this ability be invoked now? |
| `.is_active(name) -> bool` | Is the effect currently running? |
| `.charges(name) -> int` | Current charges (-1 for unlimited) |
| `.time_remaining(name) -> int` | Remaining ticks on active effect |
| `.cooldown_remaining(name) -> int` | Remaining cooldown ticks |
| `.state(name) -> AbilityState or None` | Direct access to runtime state |
| `.defined_abilities() -> list[str]` | All defined names in order |
| `.definition(name) -> AbilityDef or None` | Look up definition |
| `.snapshot() -> dict` | Serialize runtime state |
| `.restore(data)` | Restore runtime state (re-register definitions first) |

### AbilityGuards

```python
guards = AbilityGuards()
guards.register("has_mana", lambda world, manager: ...)
guards.check("has_mana", world, manager)  # -> bool
```

Guard predicates receive `(world, manager)` and return `bool`.

### make_ability_system

```python
make_ability_system(
    manager: AbilityManager,
    guards: AbilityGuards | None = None,
    on_start=None,  # (world, ctx, ability_name) -> None
    on_end=None,    # (world, ctx, ability_name) -> None
    on_tick=None,   # (world, ctx, ability_name, remaining) -> None
) -> System
```

Returns a system that processes ability state each tick. Tick order: process newly-invoked abilities (on_start), decrement active effects (on_end for expired), tick active effects (on_tick), decrement cooldowns, regenerate charges.

## Part of [tick-engine](../../README.md)

MIT License
