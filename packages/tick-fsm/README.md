# tick-fsm

Declarative finite state machines for the tick engine. Define states and transitions as data, register guard predicates, and let the system evaluate transitions each tick.

## Install

```bash
pip install tick-fsm
```

```python
from tick_fsm import FSM, FSMGuards, make_fsm_system
```

## Quick Example

```python
from dataclasses import dataclass
from tick import Engine, World
from tick.types import TickContext
from tick_fsm import FSM, FSMGuards, make_fsm_system

@dataclass
class Energy:
    value: int = 100

# Define guard predicates
guards = FSMGuards()
guards.register("is_tired", lambda world, eid: world.get(eid, Energy).value < 20)
guards.register("is_rested", lambda world, eid: world.get(eid, Energy).value >= 80)

def on_transition(world, ctx, eid, old_state, new_state):
    print(f"[tick {ctx.tick_number}] entity {eid}: {old_state} -> {new_state}")

engine = Engine(tps=10)
e = engine.world.spawn()
engine.world.attach(e, Energy(value=10))
engine.world.attach(e, FSM(
    state="working",
    transitions={
        "working": [["is_tired", "resting"]],
        "resting": [["is_rested", "working"]],
    },
))

engine.add_system(make_fsm_system(guards, on_transition=on_transition))
engine.run(1)
# Output: [tick 1] entity 0: working -> resting
```

## API Reference

### FSM

```python
FSM(state: str, transitions: dict[str, list[list[str]]])
```

Dataclass component. The `transitions` dict maps each state to a list of `[guard_name, target_state]` pairs. On each tick, the first matching guard wins. One transition per entity per tick.

### FSMGuards

```python
guards = FSMGuards()
guards.register(name: str, fn: (World, EntityId) -> bool)
guards.check(name, world, eid) -> bool
guards.has(name) -> bool
guards.names() -> list[str]
```

Registry mapping guard name strings to callable predicates. Guards are evaluated in order -- first match triggers the transition.

### make_fsm_system

```python
make_fsm_system(guards: FSMGuards, on_transition=None) -> System
```

Returns a system that queries all `FSM` components and evaluates their transitions. The optional `on_transition` callback receives `(world, ctx, eid, old_state, new_state)`.

## Part of [tick-engine](../../README.md)

MIT License
