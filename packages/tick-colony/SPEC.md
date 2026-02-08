# tick-colony v0.1.0 — Technical Specification

## Overview

**tick-colony** is a framework layer on top of `tick>=0.2.1`, providing reusable primitives that any colony builder or roguelike simulation needs, without prescribing game-specific content.

**Package name**: `tick-colony`
**Import name**: `colony`
**Dependency**: `tick>=0.2.1`
**Target**: ~410 lines of framework code (comparable to tick itself)

### Philosophy

tick has opinions about mechanism (fixed timestep, ECS, deterministic). colony has opinions about primitives (space, time, behavior) but zero opinions about domain (what your game IS).

---

## Integration Pattern: Closure-Based DI

tick's system signature is `(World, TickContext) -> None` — we cannot change it. Framework objects with external state (Grid, EventLog) reach systems through closures:

```python
grid = Grid(30, 30)
event_log = EventLog()

def movement_system(world, ctx):
    for eid, (pos,) in world.query(Position):
        grid.move(eid, pos.x, pos.y)  # grid available via closure
```

### System Factories

Primitives that need bookkeeping logic provide factory functions that return `(World, TickContext) -> None` callables:

```python
action_system = make_action_system(on_complete=my_handler)
need_decay = make_need_decay_system(on_critical=my_handler)
modifier_tick = make_modifier_tick_system()
```

User defines what happens; framework handles the bookkeeping.

---

## Serialization Strategy

### Constraint

tick's `world.restore()` uses `ctype(**dataclasses.asdict(comp))`. Nested dataclasses break because `asdict` produces nested dicts but the constructor expects dataclass instances. All framework components use only JSON primitives and flat collections:

- `NeedSet.data: dict[str, list[float]]` — not `dict[str, Need]`
- `Modifiers.entries: list[list]` — not `list[Modifier]`
- Ergonomic helpers wrap the raw data for convenience

### ColonySnapshot Coordinator

```python
class ColonySnapshot:
    def snapshot(self, engine) -> dict  # engine.snapshot() + colony state
    def restore(self, engine, data)     # engine.restore() + rebuild grid + restore events
```

- Grid rebuilds from Position components (no redundant serialization)
- EventLog serializes its entries separately
- Everything else lives in World components already

---

## Module Specifications

### 1. `colony/grid.py` — Spatial Primitives (~110 lines)

#### Component

```python
@dataclass
class Position:
    x: int
    y: int
```

Integer grid coordinates (discrete tiles, not floats).

#### Grid Class

External state — spatial index rebuilt from Position components on restore.

**Constructor**: `Grid(width: int, height: int)`
- Sparse storage internally: `dict[tuple[int,int], set[EntityId]]` for cells, `dict[EntityId, tuple[int,int]]` for reverse lookup.

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `place` | `(eid, x, y) -> None` | Place entity on grid. Raises `ValueError` if out of bounds. |
| `move` | `(eid, x, y) -> None` | Move entity to new position. Raises `ValueError` if out of bounds, `KeyError` if entity not on grid. |
| `remove` | `(eid) -> None` | Remove entity from grid. No-op if not present. |
| `at` | `(x, y) -> frozenset[EntityId]` | Entities at tile. Empty frozenset if none. |
| `position_of` | `(eid) -> tuple[int,int] \| None` | Entity position or None. |
| `in_radius` | `(x, y, r) -> list[tuple[EntityId, int, int]]` | All entities within Chebyshev distance r. |
| `neighbors` | `(x, y, diagonal=True) -> list[tuple[int,int]]` | Valid adjacent cells within bounds. |
| `pathfind` | `(start, goal, passable=None) -> list[tuple[int,int]] \| None` | A* pathfinding with heapq. `passable` is `(x, y) -> bool` predicate (default: all passable). Returns path including start and goal, or None if unreachable. |
| `rebuild` | `(world) -> None` | Clear and rebuild from Position components in world. |

**Properties**:
- `width: int`, `height: int` — grid dimensions (read-only)

#### System Factory

```python
def make_grid_cleanup_system(grid: Grid) -> System:
```

Returns a system that removes dead entities from the grid index. Iterates grid's tracked entities, removes any not alive in world.

---

### 2. `colony/actions.py` — Multi-Tick Tasks (~55 lines)

#### Component

```python
@dataclass
class Action:
    name: str
    total_ticks: int
    elapsed_ticks: int = 0
    cancelled: bool = False
```

One action per entity at a time (ECS constraint: one component per type). Users who need queues add a separate component.

#### System Factory

```python
def make_action_system(
    on_complete: Callable[[World, TickContext, EntityId, Action], None],
    on_cancel: Callable[[World, TickContext, EntityId, Action], None] | None = None,
) -> System:
```

Each tick:
1. For each entity with Action component:
   - If `cancelled` is True: call `on_cancel` (if provided), detach Action.
   - Else: increment `elapsed_ticks`. If `elapsed_ticks >= total_ticks`: call `on_complete`, detach Action.

Callbacks receive `(world, ctx, entity_id, action)`. The Action is detached after the callback returns.

---

### 3. `colony/needs.py` — Decaying Drives (~50 lines)

#### Component

```python
@dataclass
class NeedSet:
    data: dict[str, list[float]]  # name -> [value, max_val, decay_rate, critical_threshold]
```

Flat structure for snapshot compatibility. Each entry is a 4-element list:
- `[0]` value — current value (clamped 0..max)
- `[1]` max_val — maximum value
- `[2]` decay_rate — amount subtracted per tick
- `[3]` critical_threshold — value at or below which need is critical

#### Helper Class

```python
class NeedHelper:
    @staticmethod
    def add(need_set, name, value, max_val, decay_rate, critical_threshold) -> None

    @staticmethod
    def get_value(need_set, name) -> float

    @staticmethod
    def set_value(need_set, name, value) -> None  # Clamps to [0, max]

    @staticmethod
    def is_critical(need_set, name) -> bool

    @staticmethod
    def names(need_set) -> list[str]
```

#### System Factory

```python
def make_need_decay_system(
    on_critical: Callable[[World, TickContext, EntityId, str], None] | None = None,
) -> System:
```

Each tick:
1. For each entity with NeedSet:
   - For each need: subtract `decay_rate` from value (clamp to 0).
   - If need transitions to critical (was above threshold, now at or below): call `on_critical(world, ctx, entity_id, need_name)`.

Note: `on_critical` fires on **transition**, not every tick while critical.

---

### 4. `colony/stats.py` — Attribute + Modifier System (~60 lines)

#### Components

```python
@dataclass
class StatBlock:
    data: dict[str, float]  # stat_name -> base_value

@dataclass
class Modifiers:
    entries: list[list]  # each entry: [stat_name: str, amount: float, remaining_ticks: int]
```

`remaining_ticks` semantics:
- `-1` = permanent (never expires)
- `0` = expired (removed by modifier tick system)
- `>0` = ticks remaining

#### Helper Functions

```python
def effective(stat_block: StatBlock, modifiers: Modifiers, name: str) -> float:
    """Base value + sum of all matching modifiers."""

def add_modifier(modifiers: Modifiers, stat_name: str, amount: float, duration: int = -1) -> None:
    """Append a modifier entry. duration=-1 for permanent."""

def remove_modifiers(modifiers: Modifiers, stat_name: str) -> None:
    """Remove all modifiers for a stat."""
```

#### System Factory

```python
def make_modifier_tick_system() -> System:
```

Each tick:
1. For each entity with Modifiers:
   - For each entry with `remaining_ticks > 0`: decrement by 1.
   - Remove entries with `remaining_ticks == 0`.

---

### 5. `colony/events.py` — Narrative Log (~45 lines)

#### Data Class

```python
@dataclass
class Event:
    tick: int
    type: str
    data: dict[str, Any]
```

Not a component — used internally by EventLog.

#### EventLog Class

External state — serialized separately in ColonySnapshot.

**Constructor**: `EventLog(max_entries: int = 0)` — 0 means unlimited. Positive value enables ring buffer (oldest evicted when full).

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `emit` | `(tick, type, **data) -> None` | Append event. |
| `query` | `(type=None, after=None, before=None) -> list[Event]` | Filter events. All params optional. |
| `last` | `(type) -> Event \| None` | Most recent event of type. |
| `snapshot` | `() -> list[dict]` | Serialize all events. |
| `restore` | `(data: list[dict]) -> None` | Clear and restore from data. |
| `__len__` | `() -> int` | Number of events. |

---

### 6. `colony/containment.py` — Entity Hierarchy (~45 lines)

#### Components

```python
@dataclass
class Container:
    items: list[int]  # EntityIds of contained entities
    capacity: int     # -1 = unlimited

@dataclass
class ContainedBy:
    parent: int  # EntityId of parent container
```

#### Helper Functions

All functions maintain bidirectional consistency between Container and ContainedBy.

```python
def add_to_container(world, parent: EntityId, child: EntityId) -> bool:
    """Add child to parent's container. Returns False if at capacity."""

def remove_from_container(world, parent: EntityId, child: EntityId) -> None:
    """Remove child from parent's container."""

def transfer(world, child: EntityId, old_parent: EntityId, new_parent: EntityId) -> bool:
    """Move child between containers. Returns False if new container at capacity."""

def contents(world, parent: EntityId) -> list[EntityId]:
    """Return list of items in container."""

def parent_of(world, child: EntityId) -> EntityId | None:
    """Return parent entity or None."""
```

---

### 7. `colony/snapshot.py` — Framework Snapshot Coordinator (~40 lines)

```python
class ColonySnapshot:
    def __init__(self, grid: Grid | None = None, event_log: EventLog | None = None):
        ...

    def snapshot(self, engine: Engine) -> dict:
        """Returns engine snapshot + colony state."""
        # {
        #   **engine.snapshot(),
        #   "colony": {
        #     "grid": {"width": int, "height": int},
        #     "events": [...],
        #   }
        # }

    def restore(self, engine: Engine, data: dict) -> None:
        """Restores engine + rebuilds grid + restores events."""
```

Grid is rebuilt from Position components after engine restore. EventLog entries are serialized/restored directly.

---

### 8. `colony/__init__.py` — Public API

Exports:

```python
# Components
from colony.grid import Position
from colony.actions import Action
from colony.needs import NeedSet
from colony.stats import StatBlock, Modifiers
from colony.containment import Container, ContainedBy

# Framework objects
from colony.grid import Grid
from colony.events import EventLog, Event
from colony.snapshot import ColonySnapshot

# System factories
from colony.grid import make_grid_cleanup_system
from colony.actions import make_action_system
from colony.needs import make_need_decay_system
from colony.stats import make_modifier_tick_system

# Helpers
from colony.needs import NeedHelper
from colony.stats import effective, add_modifier, remove_modifiers
from colony.containment import add_to_container, remove_from_container, transfer, contents, parent_of

# Convenience
def register_colony_components(world):
    """Register all colony component types for snapshot/restore."""
    for ctype in (Position, Action, NeedSet, StatBlock, Modifiers, Container, ContainedBy):
        world.register_component(ctype)
```

---

## Verification Criteria

1. `uv run pytest` — all tests pass
2. `uv run python -m examples.village` — runs 400 ticks, replay proof passes
3. `json.dumps(snapper.snapshot(engine))` — JSON-compatible
4. Each primitive works independently (no mandatory coupling between modules)
5. Total framework code ~410 lines
