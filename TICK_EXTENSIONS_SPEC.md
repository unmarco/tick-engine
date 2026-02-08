# tick Extensions -- Technical Specification

**Version**: 0.1
**Date**: 2026-02-07
**Status**: Draft
**Author**: W72 Spec Writer

---

## 1. Overview

Six standalone extension modules for the `tick` engine. Each provides a single reusable primitive -- spatial indexing, scheduling, event dispatch, state machines, value interpolation, or entity templates. Together they cover the mechanical concerns that recur across simulations, without prescribing domain content.

Each module is a separate Python package. Each depends only on `tick>=0.2.1`. None depend on each other. A simulation may use one, several, or all of them in any combination. The goal is composable tooling, not a framework.

### Relationship to tick

tick provides the engine: loop, clock, world, systems. These extensions provide higher-level primitives that sit on top of that engine. They follow tick's patterns exactly: dataclass components, closure-based DI, system factories, stdlib only. They do not modify or extend tick's core in any way.

### Relationship to tick-colony

tick-colony was the first framework layer built on tick. Several of its primitives (Grid, Action, NeedSet) overlap with these extensions. The extensions generalize and decouple those primitives so they can serve any simulation, not just colony builders. Section 11 describes how colony can migrate to consume these extensions, replacing its own implementations with thin domain wrappers.

---

## 2. Shared Patterns

All six modules follow the same conventions. These are not suggestions -- they are mandatory constraints.

### Serialization Constraint

tick's `world.restore()` uses `ctype(**dataclasses.asdict(comp))`. Nested dataclasses break because `asdict` produces nested dicts but the constructor expects dataclass instances. All extension components MUST use only JSON primitives and flat collections:

- `str`, `int`, `float`, `bool`, `None`
- `list[...]` of the above
- `dict[str, ...]` of the above

No nested dataclasses. No sets. No tuples (use lists). No enums (use strings).

### System Factory Pattern

tick's system signature is `(World, TickContext) -> None`. Extensions that need bookkeeping logic provide factory functions:

- Factory name: `make_<name>_system(...)`
- Factory accepts configuration (callbacks, external state) as arguments
- Factory returns a `(World, TickContext) -> None` callable
- The returned callable closes over the configuration

### Closure-Based DI

External state objects (spatial indexes, registries, buses) reach systems through closures, not globals or dependency injection containers. The user creates the object, passes it to the factory, and the returned system carries the reference.

### Component Registration

Components must be registered with `world.register_component(ctype)` before `world.restore()` can reconstruct them. Extensions that provide a snapshot coordinator should auto-register their components. Extensions that do not should document the registration requirement.

The registry key format is `f"{ctype.__module__}.{ctype.__qualname__}"`. This is how `world._registry` maps type name strings to types at restore time.

### Line Budgets

Each module targets approximately 200 lines or fewer of implementation code, excluding tests. This is a guideline, not a hard ceiling -- clarity wins over brevity, but bloat is a design smell.

### Python Version

Python 3.11+ required. All modules use `from __future__ import annotations` for PEP 604 union syntax.

---

## 3. Module 1: tick-spatial -- Spatial Indexing

A collection of spatial index implementations sharing a common protocol. Provides 2D grid, 3D grid, and hex grid topologies, plus A* pathfinding.

**Package name**: `tick-spatial`
**Import name**: `spatial`
**Dependency**: `tick>=0.2.1`
**Target**: ~200 lines

### Component

**Pos2D** -- a 2D position with float coordinates.

| Field | Type | Description |
|-------|------|-------------|
| `x` | `float` | X coordinate |
| `y` | `float` | Y coordinate |

Float coordinates, not integers. This distinguishes Pos2D from colony's `Position` (integer grid tiles). Pos2D represents continuous space; the spatial indexes discretize it internally.

### SpatialIndex Protocol

All grid types implement this protocol. It is a `typing.Protocol`, not a base class. No inheritance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `place` | `(eid: EntityId, x: int, y: int) -> None` | Place entity at cell. Raises `ValueError` if out of bounds. If entity already placed, removes from old position first. |
| `move` | `(eid: EntityId, x: int, y: int) -> None` | Move entity to new cell. Raises `ValueError` if out of bounds, `KeyError` if entity not on grid. |
| `remove` | `(eid: EntityId) -> None` | Remove entity from index. No-op if not present. |
| `at` | `(x: int, y: int) -> frozenset[EntityId]` | All entities at cell. Empty frozenset if none. |
| `position_of` | `(eid: EntityId) -> tuple[int, ...] | None` | Entity's cell coordinates or None. Returns tuple[int, int] for 2D/hex, tuple[int, int, int] for 3D. |
| `in_radius` | `(x: int, y: int, r: int) -> list[tuple[EntityId, int, ...]]` | All entities within distance r of (x, y). Distance metric is topology-dependent (see below). Returns list of `(eid, x, y)` or `(eid, x, y, z)`. |
| `neighbors` | `(x: int, y: int) -> list[tuple[int, ...]]` | Valid adjacent cells within bounds. Adjacency is topology-dependent. |
| `rebuild` | `(world: World) -> None` | Clear index and rebuild from Pos2D components in world. Discretizes float coordinates to integer cells. |

**Note**: The protocol as defined uses 2D signatures (`x: int, y: int`). Grid2D and HexGrid conform naturally. Grid3D (deferred to a future release) would need 3D signatures, which creates a protocol mismatch. See "Known Issues & Future Work" below.

### Grid2D Class

2D integer grid spatial index. Chebyshev distance (king moves).

**Constructor**: `Grid2D(width: int, height: int)`

Internal storage: `dict[tuple[int,int], set[EntityId]]` for cells, `dict[EntityId, tuple[int,int]]` for reverse lookup. Same sparse approach as colony's Grid.

**Properties**: `width: int`, `height: int` (read-only)

Neighbors: 8-directional (including diagonals). No `diagonal` parameter -- always includes diagonals. Simulations wanting 4-directional movement should filter in user code.

Distance metric for `in_radius`: Chebyshev distance (`max(abs(dx), abs(dy))`).

`rebuild` discretization: `int(x)`, `int(y)` from Pos2D. Truncation toward zero, matching Python's `int()` on floats.

### Grid3D Class (Deferred)

**Deferred to a future release.** Grid3D requires 3D method signatures (`place(eid, x, y, z)`, `neighbors(x, y, z)`, etc.) that do not conform to the 2D SpatialIndex protocol. Implementing it now would either break the protocol contract or require `*args` hacks that weaken type safety. See "Known Issues & Future Work" below for the planned resolution.

The full Grid3D design (26-directional neighbors, 3D Chebyshev distance, `depth` property) is retained here for reference and will be implemented once the protocol dimensionality issue is resolved.

### HexGrid Class

Hex grid using axial coordinates (q, r). Flat-top orientation.

**Constructor**: `HexGrid(width: int, height: int)`

Width and height define the bounding rectangle in axial space: `0 <= q < width`, `0 <= r < height`.

**Properties**: `width: int`, `height: int` (read-only)

Neighbors: 6-directional. Axial neighbor offsets: `(+1,0), (-1,0), (0,+1), (0,-1), (+1,-1), (-1,+1)`.

Distance metric for `in_radius`: hex distance = `(abs(dq) + abs(dq + dr) + abs(dr)) / 2` (derived from cube coordinates).

`rebuild` discretization: `int(x)` maps to q, `int(y)` maps to r from Pos2D.

### Pathfinding

A* pathfinding is a standalone function, not a method on the grids. It operates on any `SpatialIndex` implementation.

| Function | Signature | Description |
|----------|-----------|-------------|
| `pathfind` | `(index: SpatialIndex, start: tuple[int, ...], goal: tuple[int, ...], cost: Callable[[tuple[int, ...], tuple[int, ...]], float] | None = None, walkable: Callable[[tuple[int, ...]], bool] | None = None) -> list[tuple[int, ...]] | None` | A* search. Returns path including start and goal, or None if unreachable. |

Parameters:
- `index` -- any SpatialIndex, used for `neighbors()` to determine adjacency
- `start` -- starting cell coordinates
- `goal` -- goal cell coordinates
- `cost` -- optional callable `(from_cell, to_cell) -> float`. Default: 1.0 for all moves. Allows weighted terrain.
- `walkable` -- optional callable `(cell) -> bool`. Default: all cells walkable. Cells returning False are impassable.

Heuristic: determined by the topology. Grid2D/Grid3D use Chebyshev distance. HexGrid uses hex distance. The `pathfind` function should call `index.neighbors()` for adjacency and needs a heuristic. Since the function does not know the topology, the SpatialIndex protocol should include a `heuristic` method:

| Method | Signature | Description |
|--------|-----------|-------------|
| `heuristic` | `(a: tuple[int, ...], b: tuple[int, ...]) -> float` | Admissible heuristic distance between two cells. |

Add this to the SpatialIndex protocol.

### System Factory

| Factory | Signature | Description |
|---------|-----------|-------------|
| `make_spatial_cleanup_system` | `(index: SpatialIndex) -> System` | Returns system that removes dead entities from the index. Same pattern as colony's `make_grid_cleanup_system`. |

### Design Decisions

**Why float coordinates in Pos2D?** Grid2D accepts integers. Pos2D stores floats. The discretization happens at the index boundary. This lets Pos2D serve simulations with sub-cell movement (tweening, physics) while the spatial index operates on discrete cells. Colony's `Position` uses integers because colony has no sub-cell concept; tick-spatial is more general.

**Why separate classes per topology?** A single class with a topology parameter would need conditional logic in every method. Separate classes keep each implementation simple and independently testable. The protocol ensures they are interchangeable where needed.

**Why a standalone pathfind function?** Pathfinding is not intrinsic to spatial indexing. Making it a method couples pathfinding algorithm choice to the grid class. A standalone function can be replaced or extended without touching grid code. Colony bundled pathfinding into Grid for convenience; tick-spatial decouples it.

**Why no auto-sync with World?** Matching colony's approach. Explicit `place`/`move`/`remove` calls give the user full control over when the index updates. Auto-sync would require hooks or observers, which tick deliberately does not have.

### Known Issues & Future Work

**Protocol dimensionality mismatch.** The SpatialIndex protocol is defined with 2D signatures: `place(eid, x, y)`, `neighbors(x, y)`, `at(x, y)`, `in_radius(x, y, r)`. This works for Grid2D and HexGrid, but Grid3D needs 3D signatures: `place(eid, x, y, z)`, `neighbors(x, y, z)`, etc.

This is a fundamental tension. Possible resolutions for a future release:

1. **Generic protocol with coordinate tuples.** Change all methods to accept `coord: tuple[int, ...]` instead of positional `x, y` args. Pro: one protocol fits all dimensionalities. Con: less ergonomic (`grid.place(eid, (3, 4))` instead of `grid.place(eid, 3, 4)`), and tuple unpacking adds boilerplate.

2. **Separate protocols per dimensionality.** `SpatialIndex2D` and `SpatialIndex3D`. Pro: type-safe, explicit. Con: `pathfind()` would need to accept `Union[SpatialIndex2D, SpatialIndex3D]` or use a minimal shared protocol.

3. **Base protocol + dimensional extensions.** A minimal `SpatialIndex` with only dimension-agnostic methods (`remove`, `position_of`, `rebuild`) and dimension-specific subprotocols. Pro: incremental. Con: still needs the pathfind function to know which protocol it's dealing with.

4. **`*args` with runtime arity checks.** Keep one protocol, use `*coords: int` for all spatial methods. Pro: simple. Con: loses type safety, errors only at runtime.

For v0.1, the pragmatic choice is to ship Grid2D and HexGrid (both conform cleanly to the 2D protocol), defer Grid3D, and revisit the protocol design when a 3D use case actually materializes. Option 1 (coordinate tuples) is the likely winner for v0.2.

### Project Structure

```
spatial/
    __init__.py       -- Public API re-exports
    types.py          -- Pos2D component, SpatialIndex protocol
    grid2d.py         -- Grid2D implementation
    hexgrid.py        -- HexGrid implementation
    pathfind.py       -- A* pathfinding function
    systems.py        -- make_spatial_cleanup_system
tests/
    test_grid2d.py
    test_hexgrid.py
    test_pathfind.py
pyproject.toml
```

### Line Budget

~160 lines across all source files (without Grid3D). Grid2D should be the largest (~60 lines) since it is the reference implementation. Pathfinding is ~40 lines.

---

## 4. Module 2: tick-schedule -- Scheduling and Timers

Countdown timers and periodic triggers as ECS components, with system factories that handle the bookkeeping.

**Package name**: `tick-schedule`
**Import name**: `schedule`
**Dependency**: `tick>=0.2.1`
**Target**: ~80 lines

### Components

**Timer** -- one-shot countdown. Auto-detaches after firing its callback.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Identifier for the timer (e.g., "build", "heal"). Used by callbacks to distinguish timers. |
| `remaining` | `int` | (required) | Ticks remaining. Decremented each tick. Fires when reaching 0. |

**Periodic** -- repeating trigger. Stays attached and resets after firing.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Identifier for the periodic trigger. |
| `interval` | `int` | (required) | Number of ticks between fires. |
| `elapsed` | `int` | `0` | Ticks since last fire. Incremented each tick. Fires when `elapsed >= interval`, then resets to 0. |

### System Factories

| Factory | Signature | Description |
|---------|-----------|-------------|
| `make_timer_system` | `(on_fire: Callable[[World, TickContext, EntityId, Timer], None]) -> System` | Returns system that decrements all Timer components and fires callback when they reach 0. |
| `make_periodic_system` | `(on_fire: Callable[[World, TickContext, EntityId, Periodic], None]) -> System` | Returns system that increments all Periodic components and fires callback at each interval. |

#### Timer System Behavior (per tick)

1. For each entity with a Timer component:
   a. Decrement `remaining` by 1.
   b. If `remaining <= 0`: detach Timer from entity, then call `on_fire(world, ctx, entity_id, timer)`.

Detach happens BEFORE the callback. The callback receives the detached Timer object (still valid in memory, `remaining` at 0 or below). This ordering enables timer chaining: the callback may attach a new Timer to the same entity without the subsequent detach stomping it.

#### Periodic System Behavior (per tick)

1. For each entity with a Periodic component:
   a. Increment `elapsed` by 1.
   b. If `elapsed >= interval`: call `on_fire(world, ctx, entity_id, periodic)`, then set `elapsed` to 0.

Periodic is never auto-detached. The callback may detach it explicitly if the repeating behavior should stop.

### Callback Signatures

| Callback | Signature | When Called |
|----------|-----------|------------|
| Timer `on_fire` | `(world: World, ctx: TickContext, eid: EntityId, timer: Timer) -> None` | Timer reaches 0 |
| Periodic `on_fire` | `(world: World, ctx: TickContext, eid: EntityId, periodic: Periodic) -> None` | Periodic interval completes |

### Design Decisions

**Why auto-detach Timer but not Periodic?** A timer is a one-shot event: "do X after N ticks." Once it fires, the component has no further purpose. Leaving it attached would be dead state. A periodic trigger is ongoing: "do X every N ticks." Detaching it would stop the behavior, which should be an explicit user decision.

**Why `name` on both components?** An entity might have domain reasons to know which timer fired. The name also aids debugging. Without it, callbacks would need to infer intent from context alone.

**Why tick-based (integers) instead of time-based (floats)?** Ticks are the atomic unit in tick's deterministic model. Floating-point durations would require conversion to ticks anyway, and the conversion introduces rounding questions. Integer tick counts are exact and serializable without precision loss.

### Colony Migration

Colony's `Action` component is structurally identical to `Timer` plus a `cancelled` flag. Migration path:

- `Action(name, total_ticks, elapsed_ticks, cancelled)` becomes a `Timer(name, remaining=total_ticks - elapsed_ticks)` with cancellation handled externally (detach the Timer to cancel).
- Colony's birth-interval check (manual tick counting in systems) becomes a `Periodic`.
- `make_action_system(on_complete, on_cancel)` can be replaced by `make_timer_system(on_fire)` plus external cancellation logic.

### Project Structure

```
schedule/
    __init__.py       -- Public API re-exports
    components.py     -- Timer, Periodic dataclasses
    systems.py        -- make_timer_system, make_periodic_system
tests/
    test_timer.py
    test_periodic.py
pyproject.toml
```

---

## 5. Module 3: tick-signal -- Event Bus

An in-process pub/sub event bus that queues signals and flushes them once per tick. Optionally backed by Redis Streams for cross-process communication.

**Package name**: `tick-signal`
**Import name**: `signals` (not `signal` — avoids clash with Python stdlib `signal` module)
**Dependency**: `tick>=0.2.1`
**Target**: ~120 lines

### SignalBus Class

In-memory event bus. Signals are queued during the tick and dispatched during flush.

**Constructor**: `SignalBus()`

No configuration. The bus starts empty with no subscribers and no queued signals.

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `subscribe` | `(signal_name: str, handler: Callable) -> None` | Register a handler for a signal name. Multiple handlers per signal allowed. Handlers called in registration order. |
| `publish` | `(signal_name: str, **data) -> None` | Enqueue a signal with keyword data. NOT dispatched immediately. |
| `flush` | `() -> None` | Dispatch all queued signals to their handlers, in FIFO order. Clears the queue after dispatch. Signals published during flush are queued for the NEXT flush, not dispatched in the current one. |
| `clear` | `() -> None` | Clear all queued signals without dispatching. Does not remove subscriptions. |
| `unsubscribe` | `(signal_name: str, handler: Callable) -> None` | Remove a specific handler. No-op if handler not subscribed. |

**Internal storage**:
- Subscriptions: `dict[str, list[Callable]]` -- signal name to ordered list of handlers
- Queue: `list[tuple[str, dict[str, Any]]]` -- FIFO queue of `(signal_name, data)` pairs

### Handler Signature

Handlers receive the signal name and the keyword data as a dict:

`(signal_name: str, data: dict[str, Any]) -> None`

Data is a plain dict, not kwargs. This avoids handler signature mismatches when different publishers send different keys for the same signal name.

### System Factory

| Factory | Signature | Description |
|---------|-----------|-------------|
| `make_signal_system` | `(bus: SignalBus) -> System` | Returns system that calls `bus.flush()` once per tick. |

The signal system should typically be registered LAST in the system pipeline, after all systems that might publish signals. This ensures all signals from the current tick are collected before dispatch.

### RedisSignalBus Class

Same interface as SignalBus, backed by Redis Streams. Optional -- depends on `redis` package at runtime. If `redis` is not installed, importing `RedisSignalBus` should raise `ImportError` with a clear message.

**Constructor**: `RedisSignalBus(redis_url: str, channel: str)`

- `redis_url` -- Redis connection string (e.g., `redis://localhost:6379`)
- `channel` -- Redis stream key (e.g., `tick:signals`)

**Behavior differences from SignalBus**:
- `publish` writes to the Redis stream instead of an in-memory queue
- `flush` reads from the Redis stream (using `XREAD`) and dispatches to local handlers
- `subscribe` and `unsubscribe` are local-only (handler registry is in-memory, not shared)
- Cross-process: multiple processes can publish to the same stream; each process's flush reads new entries

**Consumer group**: RedisSignalBus should use a Redis consumer group so that each process instance reads messages exactly once. Consumer group name derived from `channel` (e.g., `{channel}:consumers`).

### Design Decisions

**Why queued flush-per-tick, not immediate dispatch?** Immediate dispatch causes cascading: signal A triggers handler that publishes signal B, which triggers handler that publishes signal C, all within the same system call. This is hard to reason about, hard to debug, and can cause infinite loops. Queued flush ensures all signals from tick N are dispatched at a known point, and any signals they trigger are deferred to tick N+1 (or next flush). This matches tick's philosophy of deterministic, sequential processing.

**Why not replace colony's EventLog?** EventLog and SignalBus solve different problems. EventLog is a queryable historical record ("what happened in the last 50 ticks?"). SignalBus is a dispatch mechanism ("when X happens, do Y"). A simulation might use both: publish a signal AND log an event for the same occurrence. They are complementary, not competing.

**Why a dict for handler data instead of kwargs?** Passing `**data` to handlers would require all handlers for a signal to accept the exact same keyword arguments. A dict is more forgiving and explicitly documented.

**Why is RedisSignalBus optional?** tick's philosophy is stdlib-only. Redis support is useful for multi-process simulations but should not force a dependency on everyone. Runtime import check keeps the package dependency-free by default.

### Project Structure

```
signals/
    __init__.py       -- Public API re-exports
    bus.py            -- SignalBus class
    systems.py        -- make_signal_system
tests/
    test_bus.py
    test_system.py
pyproject.toml
```

Note: RedisSignalBus is deferred as an exercise for the developer on extending the extensions.

---

## 6. Module 4: tick-fsm -- Finite State Machines

Declarative finite state machines as ECS components. Transition rules are data (serializable). Guard logic is code (registered separately).

**Package name**: `tick-fsm`
**Import name**: `fsm`
**Dependency**: `tick>=0.2.1`
**Target**: ~90 lines

### Component

**FSM** -- a finite state machine attached to an entity.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `state` | `str` | (required) | Current state name (e.g., "idle", "foraging", "resting"). |
| `transitions` | `dict[str, list[list[str]]]` | (required) | Transition table. Keys are state names. Values are lists of `[guard_name, target_state]` pairs, evaluated in order. |

Example transitions value:

```
{
  "idle":     [["hungry", "foraging"], ["tired", "resting"]],
  "foraging": [["full", "idle"], ["tired", "resting"]],
  "resting":  [["rested", "idle"]]
}
```

For the "idle" state, the FSM first checks the "hungry" guard. If it returns True, transition to "foraging". Otherwise, check "tired". If True, transition to "resting". If no guard matches, stay "idle".

The transitions structure is flat JSON (dict of lists of lists of strings). No nested objects. Fully serializable.

### FSMGuards Registry

Maps guard name strings to callable predicates.

**Constructor**: `FSMGuards()`

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `register` | `(name: str, fn: Callable[[World, EntityId], bool]) -> None` | Register a named guard function. Overwrites if name already registered. |
| `check` | `(name: str, world: World, eid: EntityId) -> bool` | Evaluate a guard. Raises `KeyError` if guard name not registered. |
| `has` | `(name: str) -> bool` | Check if a guard name is registered. |
| `names` | `() -> list[str]` | List all registered guard names. |

Guard functions receive `(world, entity_id)` and return `bool`. They inspect the entity's components to determine if the condition is met. For example, a "hungry" guard checks whether the entity's hunger need is critical.

### System Factory

| Factory | Signature | Description |
|---------|-----------|-------------|
| `make_fsm_system` | `(guards: FSMGuards, on_transition: Callable[[World, TickContext, EntityId, str, str], None] | None = None) -> System` | Returns system that evaluates FSM transitions each tick. |

#### FSM System Behavior (per tick)

1. For each entity with an FSM component:
   a. Look up `fsm.transitions[fsm.state]` to get the list of `[guard_name, target_state]` pairs for the current state.
   b. If the current state has no transitions entry, skip (entity stays in current state).
   c. Evaluate guards in order. For each `[guard_name, target_state]`:
      - Call `guards.check(guard_name, world, entity_id)`.
      - If True: set `fsm.state = target_state`, call `on_transition(world, ctx, entity_id, old_state, new_state)` if provided, and stop evaluating further guards.
   d. If no guard matches, entity remains in its current state.

Only one transition per entity per tick. This prevents oscillation (transitioning from A to B and back to A in the same tick).

### Callback Signature

| Callback | Signature | When Called |
|----------|-----------|------------|
| `on_transition` | `(world: World, ctx: TickContext, eid: EntityId, old_state: str, new_state: str) -> None` | FSM transitions from one state to another |

The callback fires AFTER `fsm.state` has been updated. The callback may inspect or mutate the entity (e.g., start a Timer when entering "foraging" state).

### Design Decisions

**Why store transitions in the component?** Transitions are data, not logic. Storing them in the component means they serialize with the entity. Different entities can have different transition tables (e.g., a worker and a soldier have different behavioral FSMs). A separate transition registry would add indirection without benefit.

**Why store guards in a separate registry?** Guards are functions -- they cannot be serialized. Keeping them in a registry that is NOT part of the component means:
- Components are pure data (serializable).
- Guard logic can be redefined between snapshot and restore.
- Different scenarios can share FSM structure but supply different guard implementations.

**Why list-of-lists instead of dict-of-dicts for transitions?** Order matters. Guards are evaluated top to bottom; the first match wins. A dict does not guarantee order (though Python 3.7+ dicts are insertion-ordered, the semantics are clearer with an explicit list). Lists of lists also serialize as JSON arrays, which are more compact than objects.

**Why one transition per tick?** Allowing multiple transitions per tick (chaining) makes behavior harder to predict and debug. One transition per tick matches tick's philosophy: one discrete step at a time.

### Colony Migration

Colony's `decision_system` uses imperative if/elif chains to determine entity behavior. With tick-fsm:

- Define FSM transitions as data in the scenario configuration.
- Register guards that check colony's NeedSet/StatBlock conditions.
- Replace `decision_system` with `make_fsm_system(guards, on_transition=start_action)`.
- The `on_transition` callback starts the appropriate Action (or Timer) for the new state.

This separates "what transitions are possible" (data) from "what conditions trigger them" (guards) from "what happens on transition" (callback).

### Project Structure

```
fsm/
    __init__.py       -- Public API re-exports
    components.py     -- FSM dataclass
    guards.py         -- FSMGuards registry
    systems.py        -- make_fsm_system
tests/
    test_fsm.py
    test_guards.py
pyproject.toml
```

---

## 7. Module 5: tick-tween -- Value Interpolation

Smooth value changes over time as ECS components. Attach a Tween to an entity, and the tween system gradually interpolates a field on another component from one value to another over a specified number of ticks.

**Package name**: `tick-tween`
**Import name**: `tween`
**Dependency**: `tick>=0.2.1`
**Target**: ~90 lines

### Component

**Tween** -- an active interpolation attached to an entity.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target` | `str` | (required) | Component type name string, as stored in `world._registry` (e.g., `"colony.stats.StatBlock"`). Resolved to a type at runtime. |
| `field` | `str` | (required) | Field name on the target component to interpolate (e.g., `"x"`, or a dict key if the field is a dict). |
| `start_val` | `float` | (required) | Starting value of the interpolation. |
| `end_val` | `float` | (required) | Ending value of the interpolation. |
| `duration` | `int` | (required) | Total ticks for the interpolation. Must be >= 1. |
| `elapsed` | `int` | `0` | Ticks elapsed so far. |
| `easing` | `str` | `"linear"` | Easing function name. One of: `"linear"`, `"ease_in"`, `"ease_out"`, `"ease_in_out"`. |

All fields are JSON primitives (str, float, int). Fully serializable.

### Easing Functions

Four easing functions, all with signature `(t: float) -> float` where t is in [0, 1] and the return is in [0, 1]:

| Name | Formula | Curve |
|------|---------|-------|
| `linear` | `t` | Constant rate |
| `ease_in` | `t * t` | Slow start, fast end (quadratic) |
| `ease_out` | `t * (2 - t)` | Fast start, slow end (quadratic) |
| `ease_in_out` | `2*t*t` if t < 0.5, else `1 - (-2*t + 2)^2 / 2` | Slow start and end, fast middle |

The easing function registry is a simple dict mapping name strings to functions. It is module-level, not a class. Adding custom easings is possible by inserting into this dict, but the four above are the only ones provided.

### System Factory

| Factory | Signature | Description |
|---------|-----------|-------------|
| `make_tween_system` | `(on_complete: Callable[[World, TickContext, EntityId, Tween], None] | None = None) -> System` | Returns system that advances all Tweens each tick. |

#### Tween System Behavior (per tick)

1. For each entity with a Tween component:
   a. Increment `elapsed` by 1.
   b. Compute progress: `t = min(elapsed / duration, 1.0)`.
   c. Look up easing function by `tween.easing` name. Apply it: `eased_t = easing_fn(t)`.
   d. Compute interpolated value: `value = start_val + (end_val - start_val) * eased_t`.
   e. Resolve target component type from `tween.target` via `world._registry[tween.target]`.
   f. Get the target component from the entity: `target_comp = world.get(eid, target_type)`.
   g. Set the field: if `field` refers to a simple attribute, set it directly. If the target component's field is a dict, treat `field` as a dict key.
   h. If `elapsed >= duration`: set field to `end_val` exactly (avoid float drift), detach Tween from entity, then call `on_complete(world, ctx, eid, tween)` if provided. Detach-before-callback enables chaining (callback can attach a new Tween without it being stomped).

**Field resolution strategy**: Use `hasattr`/`setattr` first. If the target component has the field as an attribute, set it directly. If not, check if the component has a dict-type attribute and the field is a key in it. The code-writer should keep this resolution simple -- supporting one level of attribute access is sufficient. Nested paths (e.g., `"data.hunger"`) are out of scope.

**Error handling**: If the target component type is not in `world._registry`, or the entity does not have the target component, or the field does not exist, skip silently (log a warning if logging is available, but do not crash). Tweens on dead or incompatible entities should be cleaned up gracefully.

### Callback Signature

| Callback | Signature | When Called |
|----------|-----------|------------|
| `on_complete` | `(world: World, ctx: TickContext, eid: EntityId, tween: Tween) -> None` | Tween finishes (elapsed >= duration) |

The callback fires AFTER the final value is set and AFTER the Tween is detached. The callback may attach a new Tween (chaining) without the detach stomping it.

### Design Decisions

**Why target by type name string?** A type reference (`type` object) is not JSON-serializable. The component must serialize cleanly via `dataclasses.asdict`. Using the registry key string (`"module.ClassName"`) means the Tween can be snapshotted and restored. The same string format is already used by `world._registry`, so resolution is a single dict lookup.

**Why auto-detach on completion?** Same rationale as Timer. A completed Tween has no further purpose. Leaving it attached would be dead state.

**Why quadratic easing?** Quadratic curves are the simplest non-linear easings. They are easy to compute, easy to understand, and sufficient for most interpolation needs. Cubic or elastic easings can be added to the module-level dict by users who need them.

**Why skip silently on missing targets?** A Tween might outlive its target (e.g., entity loses the target component mid-tween). Crashing the entire system because one tween targets a missing component is disproportionate. Skipping is safe; the Tween will still be detached when it completes.

### Colony Migration

Colony currently does not have interpolation. tick-tween enables smooth transitions that were previously impossible:

- Gradually changing a stat value over N ticks instead of setting it instantly.
- Smoothly moving need values (e.g., hunger gradually increasing via tween instead of discrete decay steps).
- Progress bar effects for long-running actions.

### Project Structure

```
tween/
    __init__.py       -- Public API re-exports
    components.py     -- Tween dataclass
    easing.py         -- Easing functions and registry dict
    systems.py        -- make_tween_system
tests/
    test_tween.py
    test_easing.py
pyproject.toml
```

---

## 8. Module 6: tick-blueprint -- Entity Templates

A registry of entity recipes that can be instantiated with a single call. Recipes are pure data (JSON-serializable dicts). Spawning resolves component types through the world's registry and creates fully-assembled entities.

**Package name**: `tick-blueprint`
**Import name**: `blueprint`
**Dependency**: `tick>=0.2.1`
**Target**: ~70 lines

### BlueprintRegistry Class

Stores and instantiates entity templates.

**Constructor**: `BlueprintRegistry()`

No configuration. Starts empty.

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `define` | `(name: str, recipe: dict[str, dict[str, Any]]) -> None` | Define a named template. Overwrites if name already exists. |
| `spawn` | `(world: World, name: str, overrides: dict[str, dict[str, Any]] | None = None) -> EntityId` | Create an entity from a template. Returns the new entity ID. Raises `KeyError` if name not defined. |
| `recipes` | `() -> dict[str, dict[str, dict[str, Any]]]` | Return a copy of all defined recipes. For serialization/inspection. |
| `has` | `(name: str) -> bool` | Check if a recipe name is defined. |
| `remove` | `(name: str) -> None` | Remove a recipe. Raises `KeyError` if not defined. |

### Recipe Format

A recipe is a dict mapping component type name strings to dicts of field values:

```
{
    "spatial.types.Pos2D": {"x": 5.0, "y": 10.0},
    "colony.needs.NeedSet": {"data": {"hunger": [100, 100, 1.0, 20]}},
    "colony.stats.StatBlock": {"data": {"speed": 1.0, "strength": 5.0}}
}
```

Keys are registry key strings (same format as `world._registry` keys: `"module.ClassName"`). Values are dicts of constructor keyword arguments for the component dataclass.

### Spawn Behavior

1. Look up the recipe by name. Raise `KeyError` if not found.
2. If `overrides` is provided, shallow-merge per component: for each component name in overrides, update the recipe's field dict with the override's field dict. Overrides can add new components not in the original recipe.
3. Create a new entity via `world.spawn()`.
4. For each component in the (merged) recipe:
   a. Resolve the component type via `world._registry[component_type_name]`. Raise `KeyError` if not registered.
   b. Instantiate the component: `ctype(**field_dict)`.
   c. Attach to the entity: `world.attach(eid, component_instance)`.
5. Return the entity ID.

**Override merging**: Shallow merge at the field level, not deep merge. If a recipe has `"StatBlock": {"data": {"speed": 1.0, "strength": 5.0}}` and the override has `"StatBlock": {"data": {"speed": 2.0}}`, the result is `"StatBlock": {"data": {"speed": 2.0}}` -- the override's `data` dict REPLACES the recipe's `data` dict entirely. This is deliberate: deep merging nested dicts is ambiguous and error-prone. Users who want partial updates should construct the full field value in the override.

### Design Decisions

**Why resolve via `world._registry`?** The registry already exists for snapshot/restore. Reusing it means blueprints work with any component type that has been registered, without needing a separate type registry. Components must be registered before `spawn` is called -- the same requirement as `restore`.

**Why shallow merge for overrides?** Deep merging nested dicts requires decisions about list behavior (append? replace?), None handling, and type-specific logic. Shallow merge is predictable: each field in the override replaces the corresponding field in the recipe. The user controls what they override.

**Why store recipes as plain dicts?** Recipes are data, not logic. Plain dicts serialize to JSON trivially. This means recipes can be loaded from configuration files, sent over the network, or stored in a database. No special types needed.

**Why not store recipes in a component?** Recipes are templates, not per-entity state. Storing them in the world's ECS would mean attaching them to a "registry entity," which is a misuse of the ECS pattern. A separate registry object is cleaner.

### Colony Migration

Colony's entity creation logic is currently imperative:

- `_spawn_colonist()` in the village example manually spawns an entity and attaches Position, Action, NeedSet, StatBlock, etc.
- Stockpile setup manually spawns and attaches Container.

With tick-blueprint:

- Define a "colonist" recipe and a "stockpile" recipe in the scenario configuration.
- Replace `_spawn_colonist()` with `registry.spawn(world, "colonist", overrides={"spatial.types.Pos2D": {"x": x, "y": y}})`.
- Scenario configuration becomes data, not code.

### Project Structure

```
blueprint/
    __init__.py       -- Public API re-exports
    registry.py       -- BlueprintRegistry class
tests/
    test_blueprint.py
pyproject.toml
```

---

## 9. Dependency Graph

```
tick >= 0.2.1
  |
  +-- tick-spatial   (spatial)
  |
  +-- tick-schedule  (schedule)
  |
  +-- tick-signal    (signal)
  |
  +-- tick-fsm       (fsm)
  |
  +-- tick-tween     (tween)
  |
  +-- tick-blueprint (blueprint)
```

Every extension depends ONLY on `tick>=0.2.1`. No extension depends on any other extension. No extension depends on `tick-colony`.

`tick-colony` may optionally depend on any of these extensions to replace its own implementations (see Colony Migration Guide below), but that is colony's choice, not a requirement.

### Build Configuration

Each extension uses the same build setup:

- Build backend: `hatchling`
- Package manager: `uv`
- Python: `>=3.11`
- `tool.hatch.build.targets.wheel.packages` must map the import name to the package directory (e.g., `packages = ["spatial"]` for tick-spatial)
- `tool.uv.sources` with local path for tick during development (same pattern as tick-colony)

---

## 10. Colony Migration Guide

This section describes how `tick-colony` can adopt each extension, replacing internal implementations with thin wrappers or direct usage. Migration is optional and incremental -- colony can adopt one extension at a time.

### tick-spatial replaces colony/grid.py

| Colony Current | Extension Replacement | Notes |
|----------------|----------------------|-------|
| `Position(x: int, y: int)` | Keep as-is OR use `Pos2D(x: float, y: float)` | If colony keeps integer positions, it can use `Pos2D` with integer values (floats that happen to be whole numbers) or keep its own Position and call Grid2D directly. |
| `Grid(width, height)` | `Grid2D(width, height)` | API is identical. Colony's Grid becomes a direct import from tick-spatial. |
| `Grid.pathfind(start, goal, passable)` | `pathfind(grid, start, goal, walkable=passable)` | Standalone function instead of method. Slight signature change. |
| `make_grid_cleanup_system(grid)` | `make_spatial_cleanup_system(grid)` | Direct replacement. |

Colony's `Grid.rebuild(world)` queries `Position` components. tick-spatial's `Grid2D.rebuild(world)` queries `Pos2D` components. If colony keeps its own `Position`, it must call `rebuild` with a world that has `Pos2D` attached, or use `place`/`move` directly instead of `rebuild`.

### tick-schedule replaces colony/actions.py

| Colony Current | Extension Replacement | Notes |
|----------------|----------------------|-------|
| `Action(name, total_ticks, elapsed_ticks, cancelled)` | `Timer(name, remaining)` | Timer has no cancelled flag. Cancel by detaching. |
| `make_action_system(on_complete, on_cancel)` | `make_timer_system(on_fire)` | No built-in cancel callback. Handle externally. |
| Manual interval counting in systems | `Periodic(name, interval)` | Replaces ad-hoc tick counting. |

The migration trades the `cancelled` flag for explicit detach. This is simpler (no boolean state to track) but means colony's cancel logic moves to the system that decides to cancel: instead of `action.cancelled = True`, it does `world.detach(eid, Timer)`.

### tick-signal complements colony/events.py

| Colony Current | Extension Replacement | Notes |
|----------------|----------------------|-------|
| `EventLog.emit(tick, type, **data)` | `bus.publish(signal_name, **data)` + `event_log.emit(tick, type, **data)` | Use both. Bus dispatches reactions; EventLog records history. |
| Manual callback wiring in systems | `bus.subscribe(signal_name, handler)` | Decouples publishers from subscribers. |

tick-signal does NOT replace EventLog. It adds reactive dispatch. Colony systems that currently check EventLog for recent events and react could instead subscribe to signals.

### tick-fsm replaces colony's decision logic

| Colony Current | Extension Replacement | Notes |
|----------------|----------------------|-------|
| Imperative if/elif in `decision_system` | `FSM` component + `FSMGuards` registry | Declarative transitions. |
| Hardcoded state checks | Named guards (e.g., "hungry", "tired") | Guards encapsulate conditions. |
| Direct Action attachment on decision | `on_transition` callback that attaches Timer/Action | Separates decision from effect. |

Colony's `decision_system` becomes data-driven. The FSM transitions are defined in scenario configuration. The guards check NeedSet and StatBlock conditions. The `on_transition` callback starts the appropriate action.

### tick-tween is new for colony

Colony has no interpolation. tick-tween adds capabilities:

- Smooth stat transitions (e.g., gradually reduce speed when entity becomes tired).
- Visual indicators in future UI layers (progress bars, mood gauges).
- Gradual need changes for more natural-feeling simulations.

### tick-blueprint replaces colony's spawn helpers

| Colony Current | Extension Replacement | Notes |
|----------------|----------------------|-------|
| `_spawn_colonist()` function | `registry.spawn(world, "colonist")` | Recipe defines components. |
| Manual entity setup | Blueprint recipe | Data-driven entity creation. |
| Repeated boilerplate for each entity type | One `define()` per template | DRY entity definitions. |

---

## 11. What Is Explicitly Out of Scope

These are things these extensions do NOT address. Some might be appropriate for future extensions; others are deliberately excluded.

| Concern | Why It Is Out |
|---------|---------------|
| Visual/spatial rendering | No rendering of grids, hex maps, or any other output. Print statements are fine. |
| Continuous collision detection | Spatial indexes are for queries, not physics. No swept tests, no penetration resolution. |
| Hierarchical state machines | FSMs are flat. No nested states, no concurrent regions, no history states. |
| Behavior trees | tick-fsm is explicitly FSMs, not BTs. Behavior trees are a different pattern with different trade-offs. |
| Animation systems | tick-tween interpolates data values, not visual properties. There is no concept of sprites, keyframes, or animation curves. |
| Networked event bus | RedisSignalBus enables cross-process signals, but distributed consensus, guaranteed delivery, and event sourcing are out of scope. |
| Entity prefab inheritance | Blueprints are flat recipes, not composable class hierarchies. No recipe-extends-recipe. |
| Spatial queries beyond radius | No frustum queries, no ray casting, no polygon intersection. `in_radius` and `neighbors` are the only spatial queries. |
| Dynamic topology changes | Grid dimensions are fixed at construction. No resizing, no procedural generation of grid structure. |
| Tween chaining DSL | Tweens can be chained via `on_complete` callbacks. There is no fluent API for sequencing or paralleling tweens. |
| Signal replay / event sourcing | SignalBus does not store history. It dispatches and forgets. EventLog (colony) is for history. |
| FSM visualization / export | No DOT graph export, no state diagram rendering. The FSM is data; visualization is the user's problem. |
| Custom serialization | All components use tick's standard `dataclasses.asdict` / `ctype(**fields)` round-trip. No custom `__getstate__`/`__setstate__`. |

---

## 12. Verification Criteria

Each module is complete when the following hold:

### All Modules

1. `uv run pytest` passes with zero failures.
2. All components round-trip through `world.snapshot()` / `world.restore()` without data loss.
3. Each module has zero dependencies beyond `tick>=0.2.1` (except tick-signal's optional `redis`).
4. Each module works independently of all other extensions.
5. All components are dataclasses with flat JSON-primitive fields only.
6. Implementation code (excluding tests) is approximately 200 lines or fewer.
7. Python 3.11+ only. No compatibility shims for older versions.

### tick-spatial

8. Grid2D, Grid3D, and HexGrid all satisfy the SpatialIndex protocol (type checker passes).
9. `pathfind` finds shortest path on all three topologies.
10. `pathfind` with custom `cost` and `walkable` callables produces correct weighted paths.
11. `rebuild(world)` reconstructs the index from Pos2D components and matches manual placement.
12. `make_spatial_cleanup_system` removes dead entities from the index.

### tick-schedule

13. Timer fires `on_fire` exactly once, at the tick when `remaining` reaches 0.
14. Timer auto-detaches after callback returns.
15. Periodic fires `on_fire` at every interval boundary.
16. Periodic does NOT auto-detach. Stays attached and resets.
17. Timer with `remaining=1` fires on the very next tick.

### tick-signal

18. `publish` does NOT call handlers immediately.
19. `flush` dispatches all queued signals in FIFO order.
20. Signals published during `flush` (by handlers) are queued for the next flush, not dispatched in the current one.
21. `make_signal_system` calls `flush` exactly once per tick.
22. RedisSignalBus (if redis available) publishes and consumes across two bus instances on the same stream.

### tick-fsm

23. FSM transitions at most once per tick per entity.
24. Guards are evaluated in order; first match wins.
25. If no guard matches, entity stays in current state and `on_transition` is not called.
26. `on_transition` fires AFTER `fsm.state` is updated.
27. Unregistered guard name raises `KeyError`.
28. FSM with a state not in the transitions dict stays in that state (no error).

### tick-tween

29. Linear tween reaches exact `end_val` at completion (no float drift).
30. All four easing functions produce values in [0, 1] for inputs in [0, 1].
31. `ease_in(0) == 0`, `ease_in(1) == 1`, `ease_out(0) == 0`, `ease_out(1) == 1`, `ease_in_out(0) == 0`, `ease_in_out(1) == 1`.
32. Tween auto-detaches after `on_complete` callback returns.
33. Tween targeting a missing component does not crash the system.
34. Tween with `duration=1` completes on the very next tick.

### tick-blueprint

35. `spawn` creates an entity with all components from the recipe.
36. `spawn` with `overrides` merges fields (shallow) before instantiation.
37. `spawn` raises `KeyError` for undefined recipe name.
38. `spawn` raises `KeyError` for unregistered component type.
39. `recipes()` returns a copy (modifying it does not affect the registry).
40. Spawned entity can be snapshotted and restored (all components round-trip).

---

## References

- tick v0.2.1 Technical Specification (`tick/SPEC.md`)
- tick-colony v0.1.0 Technical Specification (`tick-colony/SPEC.md`)
- Robert Nystrom, [Game Programming Patterns](https://gameprogrammingpatterns.com/) -- State, Component, Game Loop patterns
- Amit Patel, [Red Blob Games: Hexagonal Grids](https://www.redblobgames.com/grids/hexagons/) -- hex grid coordinate systems and algorithms
- Amit Patel, [Red Blob Games: A* Pathfinding](https://www.redblobgames.com/pathfinding/a-star/) -- A* implementation reference
- Robert Penner, [Easing Functions](http://robertpenner.com/easing/) -- canonical easing function reference
