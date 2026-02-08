# tick-blueprint

Entity template registry for the tick engine. Define reusable recipes as plain dicts and spawn pre-configured entities from them, with optional per-spawn overrides.

## Install

```bash
pip install tick-blueprint
```

```python
from tick_blueprint import BlueprintRegistry
```

## Quick Example

```python
from dataclasses import dataclass
from tick import Engine
from tick_blueprint import BlueprintRegistry

@dataclass
class Health:
    value: int = 100

@dataclass
class Speed:
    value: float = 1.0

engine = Engine(tps=10)

# Register component types so blueprints can resolve them
engine.world.register_component(Health)
engine.world.register_component(Speed)

# Define templates using fully qualified type names
bp = BlueprintRegistry()
bp.define("soldier", {
    "tick_blueprint.registry.Health": {"value": 120},  # uses registered type key
    # In practice, keys match the module.qualname of the dataclass
})

# Spawn from template
eid = bp.spawn(engine.world, "soldier")
print(engine.world.get(eid, Health).value)  # 120

# Spawn with overrides
eid2 = bp.spawn(engine.world, "soldier", overrides={
    "tick_blueprint.registry.Health": {"value": 200},
})
print(engine.world.get(eid2, Health).value)  # 200
```

Note: recipe keys are the component's `module.qualname` string, which must match a type registered via `world.register_component()` or `world.attach()`.

## API Reference

### BlueprintRegistry

```python
registry = BlueprintRegistry()
```

| Method | Description |
|--------|-------------|
| `.define(name, recipe)` | Register a template. `recipe` is `{type_key: {field: value}}` |
| `.spawn(world, name, overrides=None)` | Create entity from template, returns `EntityId` |
| `.has(name) -> bool` | Check if a recipe is defined |
| `.recipes() -> dict` | Deep copy of all defined recipes |
| `.remove(name)` | Remove a recipe (raises `KeyError` if missing) |

The `overrides` parameter merges field values into the recipe before spawning. Existing component fields are updated; new component keys are added.

## Part of [tick-engine](../../README.md)

MIT License
