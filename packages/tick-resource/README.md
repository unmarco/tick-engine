# tick-resource

Typed resource management for the tick engine. Quantity-based inventories with resource definitions, crafting recipes, and decay. Replaces the entity-per-unit pattern with efficient `dict[str, int]` storage.

## Install

```bash
pip install tick-resource
```

```python
from tick_resource import ResourceDef, Inventory, InventoryHelper, ResourceRegistry
from tick_resource import Recipe, can_craft, craft, make_resource_decay_system
```

## Quick Example

```python
from tick_resource import Inventory, InventoryHelper, Recipe, craft

inv = Inventory()
InventoryHelper.add(inv, "wood", 10)
InventoryHelper.add(inv, "stone", 5)

planks = Recipe(name="planks", inputs={"wood": 2}, outputs={"plank": 8})
craft(inv, planks)

print(inv.slots)  # {"wood": 8, "stone": 5, "plank": 8}
```

## API Reference

### ResourceDef

```python
ResourceDef(
    name: str,                    # unique identifier
    max_stack: int = -1,          # -1 for unlimited
    properties: dict[str, Any] = {},  # arbitrary metadata
    decay_rate: int = 0,          # units lost per tick (0 = no decay)
)
```

Frozen dataclass. Validates non-empty name, max_stack >= -1, decay_rate >= 0.

### Inventory

```python
Inventory(
    slots: dict[str, int] = {},   # resource_name -> quantity
    capacity: int = -1,            # -1 for unlimited total quantity
)
```

Mutable dataclass component. Empty slots are automatically removed (key deleted when quantity reaches 0).

### InventoryHelper

```python
helper = InventoryHelper
```

| Method | Signature | Returns |
|--------|-----------|---------|
| `add` | `(inv, name, amount=1)` | `int` -- amount actually added |
| `remove` | `(inv, name, amount=1)` | `int` -- amount actually removed |
| `count` | `(inv, name)` | `int` -- current quantity |
| `total` | `(inv)` | `int` -- sum across all types |
| `has` | `(inv, name, amount=1)` | `bool` |
| `has_all` | `(inv, requirements)` | `bool` -- all `{name: qty}` met |
| `transfer` | `(source, target, name, amount=1)` | `int` -- amount transferred |
| `names` | `(inv)` | `list[str]` -- types present |
| `clear` | `(inv, name=None)` | `None` -- one type or all |

`add` respects capacity limits. `transfer` returns excess to source if target is full. All raise `ValueError` on negative amounts.

### ResourceRegistry

```python
registry = ResourceRegistry()
registry.define(ResourceDef(name="wood"))
registry.define(ResourceDef(name="food", decay_rate=2))
registry.get("wood")               # -> ResourceDef
registry.has("wood")                # -> True
registry.defined_resources()        # -> ["wood", "food"]
registry.remove("wood")
snap = registry.snapshot()
registry.restore(snap)
```

Optional -- Inventory works without it. Required for the decay system.

### Recipe

```python
Recipe(
    name: str,
    inputs: dict[str, int] = {},    # consumed
    outputs: dict[str, int] = {},   # produced
    duration: int = 0,              # metadata (ticks, not enforced)
)
```

```python
can_craft(inventory, recipe) -> bool
craft(inventory, recipe) -> bool     # atomic: all-or-nothing
```

`craft()` checks all inputs first, then consumes and produces. Returns `False` without modifying anything if inputs are insufficient. `duration` is metadata for game logic (e.g., wire to a tick-schedule Timer).

### make_resource_decay_system

```python
make_resource_decay_system(
    registry: ResourceRegistry,
    on_spoiled=None,  # (world, ctx, entity_id, resource_name, amount_lost) -> None
) -> System
```

Returns a system that decrements resources with `decay_rate > 0` each tick. Unknown resources (not in registry) are skipped.

## Part of [tick-engine](../../README.md)

MIT License
