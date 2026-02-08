# tick-tween

Smooth value interpolation over time for the tick engine. Attach a `Tween` component to animate any numeric field on any other component, with configurable easing functions.

## Install

```bash
pip install tick-tween
```

```python
from tick_tween import Tween, EASINGS, make_tween_system
```

## Quick Example

```python
from dataclasses import dataclass
from tick import Engine
from tick_tween import Tween, make_tween_system

@dataclass
class Opacity:
    value: float = 1.0

engine = Engine(tps=10)
e = engine.world.spawn()
engine.world.attach(e, Opacity(value=1.0))

# Fade from 1.0 to 0.0 over 5 ticks with ease-out
engine.world.attach(e, Tween(
    target="__main__.Opacity",  # module.qualname of the target component
    field="value",
    start_val=1.0,
    end_val=0.0,
    duration=5,
    easing="ease_out",
))

engine.add_system(make_tween_system())
engine.run(5)

print(engine.world.get(e, Opacity).value)  # 0.0
```

The tween auto-detaches when complete. To chain tweens, pass an `on_complete` callback that attaches a new `Tween`.

## API Reference

### Tween

```python
Tween(
    target: str,       # module.qualname of the component type to animate
    field: str,        # field name on the target component
    start_val: float,
    end_val: float,
    duration: int,     # in ticks
    elapsed: int = 0,
    easing: str = "linear",
)
```

Dataclass component. The `target` string must match a component type registered in the world (via `attach()` or `register_component()`).

### EASINGS

Built-in easing functions:

| Name | Curve |
|------|-------|
| `"linear"` | Constant rate |
| `"ease_in"` | Quadratic acceleration |
| `"ease_out"` | Quadratic deceleration |
| `"ease_in_out"` | Smooth acceleration then deceleration |

### make_tween_system

```python
make_tween_system(on_complete=None) -> System
```

Returns a system that advances all `Tween` components each tick. When a tween finishes, it sets the target field to `end_val`, detaches the `Tween`, and then calls `on_complete(world, ctx, eid, tween)` if provided. Detach-before-callback enables chaining.

## Part of [tick-engine](../../README.md)

MIT License
