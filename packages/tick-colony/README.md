# tick-colony

Reusable colony builder and roguelike simulation primitives for the tick engine. Provides grid-based spatial indexing with A* pathfinding, actions, needs, stats with modifiers, containment, lifecycle, and event logging.

## Install

```bash
pip install tick-colony
```

```python
import tick_colony
```

## Quick Example

```python
from tick import Engine, World
from tick.types import TickContext
from tick_colony import (
    Position, Grid, Action, NeedSet, NeedHelper,
    make_grid_cleanup_system, make_action_system,
    register_colony_components,
)

engine = Engine(tps=10)
grid = Grid(width=16, height=16)

# Spawn an entity on the grid
villager = engine.world.spawn()
engine.world.attach(villager, Position(x=5, y=3))
grid.place(villager, 5, 3)

# Give it a need
ns = NeedSet()
NeedHelper.add(ns, "hunger", value=80, max_val=100, decay_rate=2.0, critical_threshold=20)
engine.world.attach(villager, ns)

# Register systems
def on_action_done(world, ctx, eid, action):
    print(f"[tick {ctx.tick_number}] {action.name} complete for entity {eid}")

engine.add_system(make_action_system(on_complete=on_action_done))
engine.add_system(make_grid_cleanup_system(grid))
engine.run(5)
```

## Components

| Component | Fields | Description |
|-----------|--------|-------------|
| `Position` | `x: int, y: int` | Grid coordinates |
| `Action` | `name, total_ticks, elapsed_ticks, cancelled` | Timed action, auto-detaches on complete |
| `NeedSet` | `data: dict` | Collection of needs (hunger, sleep, etc.) |
| `StatBlock` | `data: dict[str, float]` | Base stat values |
| `Modifiers` | `entries: list` | Temporary stat bonuses with duration |
| `Container` | `items: list[int], capacity: int` | Holds child entities |
| `ContainedBy` | `parent: int` | Marks entity as inside a container |
| `Lifecycle` | `born_tick: int, max_age: int` | Age tracking, auto-despawn |

## Framework Objects

| Class | Description |
|-------|-------------|
| `Grid(width, height)` | Spatial index with place/move/remove, radius queries, A* pathfinding |
| `EventLog(max_entries=0)` | Ring-buffer event log with emit/query/last |
| `ColonySnapshot(grid, event_log)` | Snapshot/restore wrapper that auto-registers colony components |

## System Factories

| Factory | Description |
|---------|-------------|
| `make_action_system(on_complete, on_cancel=None)` | Ticks actions, fires callbacks on complete/cancel |
| `make_grid_cleanup_system(grid)` | Removes dead entities from the grid |
| `make_need_decay_system(on_critical=None, on_zero=None)` | Decays needs each tick |
| `make_modifier_tick_system()` | Decrements modifier durations, removes expired |
| `make_lifecycle_system(on_death=None)` | Despawns entities that exceed max_age |

## Helpers

| Function | Description |
|----------|-------------|
| `NeedHelper.add(ns, name, value, max_val, decay_rate, critical_threshold)` | Add a need |
| `NeedHelper.get_value(ns, name)` / `set_value(ns, name, value)` | Read/write need value |
| `NeedHelper.is_critical(ns, name)` | Check if need is at critical threshold |
| `effective(stat_block, modifiers, name)` | Get base + modifier total |
| `add_modifier(mods, stat_name, amount, duration)` | Add a temporary modifier |
| `remove_modifiers(mods, stat_name)` | Remove all modifiers for a stat |
| `add_to_container(world, parent, child)` | Put entity into container (respects capacity) |
| `remove_from_container(world, parent, child)` | Take entity out |
| `transfer(world, child, old_parent, new_parent)` | Move between containers |
| `contents(world, parent)` / `parent_of(world, child)` | Query containment |
| `register_colony_components(world)` | Register all colony types for snapshot/restore |

## Grid Pathfinding

```python
grid = Grid(10, 10)
path = grid.pathfind((0, 0), (5, 5), passable=lambda x, y: True)
# Returns list of (x, y) tuples, or None if unreachable
```

## Part of [tick-engine](../../README.md)

MIT License
