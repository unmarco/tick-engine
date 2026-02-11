# tick-engine API Reference

> Complete API reference for all 16 packages in the tick-engine ecosystem.
> Version: 0.14.0 | Python 3.11+ | stdlib only (zero external dependencies)
>
> **How to read this document:** Jump to a package via Quick Navigation. Each package section starts with an "At a Glance" table, followed by detailed API. Use Common Tasks to find the right starting point. Emergency Reference has the 5 things you need at 2am.

---

## Quick Navigation

| Package | Import | Key Type | Key Factory | Description |
|---------|--------|----------|-------------|-------------|
| [tick](#tick---core-engine) | `tick` | `Engine`, `World` | -- | Core engine: loop, clock, world, ECS, query filters |
| [tick-schedule](#tick-schedule---timers--periodic-triggers) | `tick_schedule` | `Timer`, `Periodic` | `make_timer_system` | Countdown timers and periodic triggers |
| [tick-fsm](#tick-fsm---finite-state-machines) | `tick_fsm` | `FSM`, `FSMGuards` | `make_fsm_system` | Declarative finite state machines (hierarchical) |
| [tick-blueprint](#tick-blueprint---entity-templates) | `tick_blueprint` | `BlueprintRegistry` | -- | Entity template registry with metadata |
| [tick-signal](#tick-signal---event-bus) | `tick_signal` | `SignalBus` | `make_signal_system` | In-process pub/sub event bus |
| [tick-tween](#tick-tween---value-interpolation) | `tick_tween` | `Tween`, `EASINGS` | `make_tween_system` | Smooth value interpolation with easing |
| [tick-spatial](#tick-spatial---spatial-indexing--pathfinding) | `tick_spatial` | `Grid2D`, `HexGrid` | `pathfind` | Grid2D, Grid3D, HexGrid, A* pathfinding |
| [tick-atlas](#tick-atlas---cell-property-maps) | `tick_atlas` | `CellDef`, `CellMap` | -- | Cell/tile property maps (terrain, movement cost) |
| [tick-physics](#tick-physics---kinematics--collisions) | `tick_physics` | `KinematicBody` | `make_physics_system` | N-dimensional kinematics and collision detection |
| [tick-event](#tick-event---world-level-event-scheduling) | `tick_event` | `EventScheduler` | `make_event_system` | World-level event scheduling with cycles |
| [tick-ability](#tick-ability---player-triggered-abilities) | `tick_ability` | `AbilityManager` | `make_ability_system` | Abilities with charges, cooldowns, effects |
| [tick-command](#tick-command---typed-command-queue) | `tick_command` | `CommandQueue` | `make_command_system` | Typed command queue with FIFO dispatch |
| [tick-resource](#tick-resource---inventories--crafting) | `tick_resource` | `Inventory` | `make_resource_decay_system` | Resource inventories, recipes, decay |
| [tick-ai](#tick-ai---behavior-trees--utility-ai) | `tick_ai` | `AIManager` | `make_bt_system` | Behavior trees, utility AI, blackboard |
| [tick-llm](#tick-llm---async-llm-strategic-layer) | `tick_llm` | `LLMManager` | `make_llm_system` | Async LLM queries with thread pool |
| [tick-colony](#tick-colony---colony-simulation-primitives) | `tick_colony` | `ColonySnapshot` | -- | Colony builder primitives (re-exports all extensions) |

---

## Common Tasks

**Setup and Engine**

| I want to... | Code |
|---|---|
| Create an engine and run it | `Engine(tps=20)` then `engine.run(100)` or `engine.step()` |
| Run with real-time pacing | `engine.run_forever()` (sleeps to match TPS; stop via `ctx.request_stop()`) |
| Save and restore game state | `data = engine.snapshot()` / `engine.restore(data)` |
| Use deterministic randomness | `ctx.random.randint(1, 6)` (seeded RNG, saved in snapshots) |

**Entities and Components**

| I want to... | Code |
|---|---|
| Spawn an entity with components | `eid = world.spawn()` then `world.attach(eid, MyComponent(...))` |
| Query entities by components | `for eid, (pos, vel) in world.query(Pos, Vel):` |
| Exclude entities from a query | `world.query(Pos, Not(Dead))` |
| Match any of several components | `world.query(AnyOf(CircleCollider, AABBCollider))` |
| React to component changes | `world.on_attach(Pos2D, lambda w, eid, comp: print(f"{eid} placed"))` |
| Register components for restore | `world.register_component(MyComp)` (before `engine.restore()`) |

**Timers, FSMs, and Effects**

| I want to... | Code |
|---|---|
| Set a one-shot timer | `world.attach(eid, Timer(name="explode", remaining=10))` |
| Set a recurring trigger | `world.attach(eid, Periodic(name="pulse", interval=5))` |
| Implement a state machine | Create `FSM(state="idle", transitions={...})` and `FSMGuards` |
| Interpolate a value over time | `world.attach(eid, Tween(target=..., field="x", start_val=0, end_val=100, duration=20))` |
| Trigger a player ability | `ability_manager.invoke("fireball", world, ctx, guards)` (ctx = TickContext from system) |

**Spatial, Physics, and AI**

| I want to... | Code |
|---|---|
| Path-find on a grid | `pathfind(grid, start, goal, walkable=cellmap.passable)` |
| Place entities on a grid | `grid.place(eid, (x, y))` then `grid.move(eid, (nx, ny))` |
| Detect collisions | `make_collision_system(on_collision=my_handler)` |
| Apply forces to a body | `body.forces.append((0.0, -9.8 * body.mass))` |
| Add AI behavior trees | `mgr.define_tree("patrol", "root", nodes)` then `world.attach(eid, BehaviorTree("patrol"))` |
| Query an LLM asynchronously | `world.attach(eid, LLMAgent(role="leader", personality="cautious", context="colony"))` |

**Colony Sim**

| I want to... | Code |
|---|---|
| Build a colony sim | `from tick_colony import Grid2D, Timer, FSM, EventLog, ColonySnapshot` |
| Snapshot everything at once | `ColonySnapshot(grid, event_log, ...).snapshot(engine)` |
| Feed colony state to LLM | `make_colony_context(grid, cellmap, event_log)` |
| Parse LLM directives | `make_directive_parser(handlers={"assign_task": handler})` |

---

## Emergency Reference

> **The 5 things you need when debugging at 2am.**

### 1. Components must be dataclasses

If `snapshot()`/`restore()` breaks, check that every component is a `@dataclass` and has **no nested dataclasses**. Restore uses `ctype(**dataclasses.asdict(comp))` which flattens nested structures into a single dict. Keep components flat -- use primitives, dicts, and lists.

### 2. Register components before restore

Call `world.register_component(MyComp)` for every component type before calling `engine.restore()`. Unregistered types raise `SnapshotError`. `attach()` auto-registers, but after a fresh `Engine()` you must manually register every type that might appear in a snapshot.

### 3. Systems run in registration order

System signature: `(World, TickContext) -> None`. Add with `engine.add_system(fn)`. They run in the order you registered them. There is no dependency resolution -- if your FSM system reads a Timer component, the timer system must run first. **You** own the execution order.

### 4. Query returns (eid, (comp1, comp2, ...))

The tuple contains components in the order you passed the types. Filter types (`Not`, `AnyOf`) are not included in the result tuple. The query iterates over the first required type's storage -- put the **rarest** component type first for best performance.

### 5. Timer/Tween detach before callback

When a `Timer` fires or a `Tween` completes, the component is **detached before** your callback runs. This lets you safely attach a new Timer/Tween in the callback (chaining). The component passed to your callback has `remaining=0` / `elapsed=duration`.

---

## tick -- Core Engine

`import tick` or `from tick import Engine, World, Clock, TickContext, Not, AnyOf`

The foundation of the entire ecosystem. Provides the tick loop, entity-component storage, queries, and snapshot/restore.

> **Why this design:** tick deliberately has zero dependencies and zero opinions about what a "game" is. It provides the skeleton of a game loop (fixed-timestep ticking, entity-component storage, deterministic RNG) and nothing else. Every game-specific behavior lives in extension packages. This makes the core testable, predictable, and reusable across wildly different simulations.

### At a Glance

| What | How |
|------|-----|
| Create engine | `e = Engine(tps=20, seed=42)` |
| Access world | `e.world` |
| Add system | `e.add_system(fn)` where `fn(world, ctx) -> None` |
| Run N ticks | `e.run(100)` |
| Run one tick | `e.step()` |
| Spawn entity | `eid = world.spawn()` |
| Attach component | `world.attach(eid, Pos(x=0, y=0))` |
| Query | `for eid, (pos,) in world.query(Pos):` |
| Exclude filter | `world.query(Pos, Not(Dead))` |
| Snapshot / restore | `data = e.snapshot()` / `e.restore(data)` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `Engine` | class | Core engine: systems, loop, snapshot/restore |
| `World` | class | Entity-component storage and queries |
| `Clock` | class | Fixed-timestep clock |
| `TickContext` | dataclass | Immutable per-tick context passed to systems |
| `EntityId` | type alias | `int` -- entity identifier |
| `Not` | class | Query filter: exclude entities with a component |
| `AnyOf` | class | Query filter: match entities with any of several components |
| `DeadEntityError` | exception | Raised when operating on a despawned entity |
| `SnapshotError` | exception | Raised on restore failures |

### Engine

The main entry point. Creates a world, a clock, and runs systems in order.

```python
class Engine:
    def __init__(self, tps: int = 20, seed: int | None = None) -> None
```

**Parameters:**
- `tps` -- Ticks per second. Determines `Clock.dt` (= `1.0 / tps`). This is the *simulation* rate, not the render rate. In a real game loop, you typically run the engine at 10-20 TPS for game logic while rendering at 60 FPS, using a tick accumulator pattern.
- `seed` -- RNG seed for deterministic simulation. Auto-generated from `os.urandom(8)` if `None`. The seed is saved in snapshots, so restore gives you deterministic replay from that point forward.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `world` | `World` | The entity-component store |
| `clock` | `Clock` | The fixed-timestep clock |
| `seed` | `int` | The RNG seed used by this engine |

**Methods:**

```python
def add_system(self, system: System) -> None
```
Register a system function. Systems execute in registration order each tick. A `System` is any callable with signature `(World, TickContext) -> None`.

> **Tip:** System order matters. A common arrangement for a colony sim:
> 1. Command system (drain player inputs)
> 2. FSM system (state transitions)
> 3. Timer/Periodic systems (countdowns)
> 4. Ability system (effects)
> 5. Physics system (movement)
> 6. Collision system (detection)
> 7. AI systems (BT + utility)
> 8. Pressure system (colony monitoring)
> 9. LLM system (async queries)
> 10. Signal system (event delivery -- flush last so all systems can publish)

> **Gotcha:** If `request_stop()` is called mid-tick, the engine breaks out of the system loop immediately -- systems registered after the one that stopped will NOT run for that tick.

```python
def on_start(self, hook: Callable[[World, TickContext], None]) -> None
def on_stop(self, hook: Callable[[World, TickContext], None]) -> None
```
Register lifecycle hooks. `on_start` hooks fire once before the first tick of `run()`/`run_forever()`. `on_stop` hooks fire once after the last tick. Not called by `step()`.

> **Gotcha:** `step()` does NOT fire start/stop hooks. If you're driving the engine externally (e.g., from a game loop calling `step()` each frame), you must handle initialization yourself.

```python
def step(self) -> None
```
Advance the engine by exactly one tick. Does not fire start/stop hooks.

```python
def run(self, n: int) -> None
```
Run for `n` ticks. Fires start hooks before the first tick, stop hooks after the last. Stops early if any system calls `ctx.request_stop()`.

```python
def run_forever(self) -> None
```
Run continuously with real-time pacing. Sleeps between ticks to match the configured TPS using `time.sleep()`. Stops when `ctx.request_stop()` is called.

> **Tip:** `run_forever()` is useful for headless simulations or servers. For games with a render loop, use `step()` inside your own loop with a tick accumulator. See the pygame demos for this pattern.

```python
def snapshot(self) -> dict[str, Any]
def restore(self, data: dict[str, Any]) -> None
```
Serialize / deserialize the full engine state (clock, RNG, all entities and components). Components must be dataclasses. Hooks and systems are NOT serialized -- re-register them after restore.

> **Why:** Snapshot/restore is intentionally limited to *data*. Systems, hooks, guard registries, and AI definitions are all code -- they belong in your setup function, not in a save file. This makes snapshots small and portable, and forces a clean separation between data and behavior.

> **Gotcha:** `restore()` suppresses all attach/detach hooks via an internal `_hooks_enabled` flag with try/finally. This prevents spurious side effects during deserialization (e.g., a spatial index trying to place entities before the grid is rebuilt).

> **Gotcha:** Nested dataclasses in components break restore. `World.restore()` does `ctype(**dataclasses.asdict(comp))` which flattens nested structures into a single dict. Keep components flat -- use primitives, dicts, and lists.

> **Gotcha:** `restore()` validates TPS -- the snapshot's TPS must match the engine's. You cannot load a 20-TPS snapshot into a 10-TPS engine.

> **See also:** [ColonySnapshot](#colonysnapshot) wraps `engine.restore()` with grid rebuilding, LLMAgent reset, and extension state restore. Use it instead of raw `engine.restore()` in colony sims.

### World

Entity-component storage with querying and lifecycle hooks.

```python
class World:
    def __init__(self) -> None
```

**Entity lifecycle:**

```python
def spawn(self) -> EntityId
```
Create a new entity. Returns a unique integer ID (monotonically increasing, never reused).

> **Why never reused:** This prevents a class of bugs where a stale entity reference accidentally operates on a new entity that happened to get the same ID. The trade-off is that entity IDs grow forever, but `int` in Python has no upper bound.

```python
def despawn(self, entity_id: EntityId) -> None
```
Remove an entity and all its components. Fires `on_detach` hooks for each removed component.

```python
def alive(self, entity_id: EntityId) -> bool
```
Check if an entity is alive.

```python
def entities(self) -> frozenset[EntityId]
```
Return all living entity IDs.

**Component operations:**

```python
def attach(self, entity_id: EntityId, component: Any) -> None
```
Add a component to an entity. The component type is inferred from `type(component)`. Fires `on_attach` hooks. Raises `DeadEntityError` if the entity is dead. Attaching the same type again overwrites silently (fires `on_attach` again).

> **Gotcha:** One component instance per type per entity. If you attach a second `Timer` to the same entity, it replaces the first. Use a single component with a list field if you need multiples (e.g., `KinematicBody.forces` is a list).

```python
def detach(self, entity_id: EntityId, component_type: type) -> None
```
Remove a component from an entity. Fires `on_detach` hooks. Silent no-op if the entity doesn't have that component.

```python
def get(self, entity_id: EntityId, component_type: type[T]) -> T
```
Get a component. Raises `DeadEntityError` if entity is dead. Raises `KeyError` if component is missing.

```python
def has(self, entity_id: EntityId, component_type: type) -> bool
```
Check if an entity has a component. Returns `False` for dead entities (does not raise).

```python
def register_component(self, ctype: type) -> None
```
Register a component type for snapshot/restore. Called automatically on `attach()`, but must be called manually before `restore()` for types not yet seen.

**Querying:**

```python
def query(self, *args: QueryArg) -> Generator[tuple[EntityId, tuple[Any, ...]], None, None]
```
Find entities matching component requirements. Arguments can be:
- **Plain types** (e.g., `Pos`, `Vel`) -- entity must have all of them. Components returned in the result tuple in this order.
- **`Not(SomeType)`** -- entity must NOT have this component. Not included in result tuple.
- **`AnyOf(A, B, C)`** -- entity must have at least one. Not included in result tuple.

```python
# Example: entities with Pos and Vel, but not Dead
for eid, (pos, vel) in world.query(Pos, Vel, Not(Dead)):
    pos.x += vel.dx * ctx.dt
```

> **Performance tip:** The query iterates over the storage of the *first required type* you pass. Put the rarest component first to minimize iterations. For example, `query(Poisoned, Health)` is faster than `query(Health, Poisoned)` if few entities are poisoned.

> **Gotcha:** The query is a generator. If you modify entities during iteration (spawn, despawn, attach, detach), you may get surprising results. The timer system wraps its query in `list()` to snapshot the candidates first: `for eid, (t,) in list(world.query(Timer))`. Do the same when your system mutates the world.

> **Gotcha:** Components in the result tuple are live references, not copies. Mutating `pos.x` directly modifies the stored component. This is by design -- no need to "write back".

**Lifecycle hooks:**

```python
def on_attach(self, ctype: type, callback: HookCallback) -> None
def on_detach(self, ctype: type, callback: HookCallback) -> None
def off_attach(self, ctype: type, callback: HookCallback) -> None
def off_detach(self, ctype: type, callback: HookCallback) -> None
```
Register/unregister callbacks for component attach/detach events. `HookCallback` signature: `(World, EntityId, component) -> None`. Hooks are suppressed during `restore()`.

> **Why suppress during restore:** Without suppression, restoring 500 entities would fire 500+ attach hooks, triggering spatial index placements, signal emissions, etc. -- all before the world is fully reconstructed. The try/finally guard ensures hooks are always re-enabled even if restore raises.

> **Tip:** Hooks are useful for keeping external data structures in sync. For example, tick-spatial uses `on_attach(Pos2D)` to auto-place entities on the grid. But remember: hooks are NOT serialized. Re-register them after restore.

**Snapshot/Restore:**

```python
def snapshot(self) -> dict[str, Any]
def restore(self, data: dict[str, Any]) -> None
```
Serialize/deserialize all entities and components. Component types must be registered via `register_component()` before `restore()`. Raises `SnapshotError` for unregistered types.

### Clock

Fixed-timestep clock tracking tick progression.

```python
class Clock:
    def __init__(self, tps: int) -> None
```

| Property | Type | Description |
|----------|------|-------------|
| `tps` | `int` | Ticks per second |
| `dt` | `float` | Seconds per tick (`1.0 / tps`) |
| `tick_number` | `int` | Current tick count (starts at 0, incremented by `advance()`) |

```python
def advance(self) -> int       # Increment tick_number, return new value
def reset(self, tick_number: int = 0) -> None  # Reset tick counter
def context(self, stop_fn: Callable[[], None], rng: random.Random) -> TickContext
```

> **Gotcha:** `Clock.context()` requires both arguments. In tests where you don't need stop functionality: `clock.context(lambda: None, random.Random(42))`.

### TickContext

Frozen dataclass passed to every system on every tick.

```python
@dataclass(frozen=True)
class TickContext:
    tick_number: int                    # Current tick
    dt: float                           # Seconds per tick
    elapsed: float                      # Total elapsed seconds (tick_number * dt)
    request_stop: Callable[[], None]    # Call to stop the engine after this tick
    random: random.Random               # Seeded RNG for deterministic randomness
```

> **Why frozen:** TickContext is immutable so systems cannot tamper with engine state. The only mutation channel is `request_stop()`, which sets a flag on the Engine.

> **Tip:** Always use `ctx.random` instead of the stdlib `random` module for simulation logic. This ensures deterministic replay from snapshots -- the RNG state is saved and restored.

### Not / AnyOf

Query filter sentinels used with `World.query()`.

```python
class Not:
    def __init__(self, ctype: type) -> None
    # Exclude entities that have this component

class AnyOf:
    def __init__(self, *ctypes: type) -> None
    # Match entities that have at least one of these component types
```

> **See also:** `tick.filters` module. `Not` and `AnyOf` are in the result of queries only for filtering -- they don't appear in the component tuple.

---

## tick-schedule -- Timers & Periodic Triggers

`from tick_schedule import Timer, Periodic, make_timer_system, make_periodic_system`

One-shot and recurring timers implemented as ECS components with system factories.

> **Why ECS-based timers:** Timers are components, not manager-level state. This means they're automatically included in snapshots, they're visible to queries (you can find all entities with active timers), and they follow the same lifecycle as everything else. No separate timer registry to maintain.

### At a Glance

| What | How |
|------|-----|
| One-shot timer | `world.attach(eid, Timer(name="boom", remaining=10))` |
| Recurring trigger | `world.attach(eid, Periodic(name="pulse", interval=5))` |
| Process timers | `engine.add_system(make_timer_system(on_fire=my_cb))` |
| Process periodics | `engine.add_system(make_periodic_system(on_fire=my_cb))` |
| Callback signature | `on_fire(world, ctx, eid, timer_or_periodic)` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `Timer` | dataclass | One-shot countdown; auto-detaches at zero |
| `Periodic` | dataclass | Recurring trigger; fires every N ticks |
| `make_timer_system` | function | System factory for processing Timers |
| `make_periodic_system` | function | System factory for processing Periodics |

### Timer

```python
@dataclass
class Timer:
    name: str          # Identifier (for your callback to distinguish timers)
    remaining: int     # Ticks until fire (decremented each tick)
```

The timer system decrements `remaining` by 1 each tick. When it hits 0, the component is **detached before** the `on_fire` callback runs.

> **Why detach-before-callback:** If the Timer were still attached when your callback fires, attaching a new Timer for chaining would silently overwrite the old one (which is about to be processed as "done"). By detaching first, the slot is clean and you can safely chain: `on_fire` -> attach new Timer -> next tick picks it up.

> **Gotcha:** The Timer is already detached when your callback fires. The timer passed to your callback has `remaining=0`. If you need the original duration for re-arming, store it externally (e.g., in a Blackboard or a custom component).

> **Gotcha:** The timer system wraps its query in `list()` to snapshot candidates before iterating. This means timers attached *during* the current tick's timer processing won't fire until the next tick.

> **See also:** [Tween](#tween) uses the identical detach-before-callback pattern. [Periodic](#periodic) never detaches -- use it for recurring triggers.

### Periodic

```python
@dataclass
class Periodic:
    name: str          # Identifier
    interval: int      # Ticks between fires
    elapsed: int = 0   # Current counter (auto-managed)
```

Fires every `interval` ticks. Never auto-detaches. `elapsed` resets to 0 after each fire.

### System Factories

```python
def make_timer_system(
    on_fire: Callable[[World, TickContext, int, Timer], None],
) -> Callable[[World, TickContext], None]
```
`on_fire(world, ctx, eid, timer)` -- called when a timer reaches zero.

```python
def make_periodic_system(
    on_fire: Callable[[World, TickContext, int, Periodic], None],
) -> Callable[[World, TickContext], None]
```
`on_fire(world, ctx, eid, periodic)` -- called every `interval` ticks.

---

## tick-fsm -- Finite State Machines

`from tick_fsm import FSM, FSMGuards, make_fsm_system`

Declarative state machines with hierarchical state support via dot-notation.

> **Why declarative:** The FSM is pure data -- transitions and guards are looked up by name string, not stored as functions. This means the FSM component serializes cleanly in snapshots. The guard functions live in FSMGuards, which is a code-only registry you re-create on startup.

### At a Glance

| What | How |
|------|-----|
| Define transitions | `FSM(state="idle", transitions={"idle": [["enemy_near", "combat"]]})` |
| Register guard | `guards.register("enemy_near", lambda w, eid: ...)` |
| Hierarchical states | Dot-notation: `"combat.attack"`, `"combat.defend"` |
| Create system | `engine.add_system(make_fsm_system(guards, on_transition=cb))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `FSM` | dataclass | State machine component |
| `FSMGuards` | class | Named guard predicate registry |
| `make_fsm_system` | function | System factory for FSM evaluation |

### FSM

```python
@dataclass
class FSM:
    state: str                                    # Current state (leaf in hierarchy)
    transitions: dict[str, list[list[str]]]       # state -> [[guard_name, target_state], ...]
    initial: dict[str, str] = {}                  # parent -> default child state
    history: dict[str, str] = {}                  # parent -> last active child (auto-managed)
```

**Transition type explained:** `dict[str, list[list[str]]]` maps each state name to a list of transition rules. Each rule is a two-element list `[guard_name, target_state]`. Guards are evaluated in order; the first that returns `True` fires.

**Hierarchical states:** Use dot-notation (e.g., `"combat.attack"`, `"combat.defend"`). Parent state transitions act as fallbacks when no transition fires for the leaf state.

**Concrete hierarchical example:**

```python
fsm = FSM(
    state="idle",
    transitions={
        "idle":           [["enemy_near", "combat"]],         # idle -> combat
        "combat":         [["enemy_dead", "idle"]],           # combat (parent) -> idle
        "combat.attack":  [["low_health", "combat.defend"]],  # attack -> defend
        "combat.defend":  [["health_ok", "combat.attack"]],   # defend -> attack
    },
    initial={"combat": "combat.attack"},  # entering "combat" resolves to "combat.attack"
)
# When entering "combat", initial resolves to "combat.attack".
# Re-entering "combat" later resumes at the last active child via history.
```

> **Tip:** The `initial` dict maps parent states to their default child. When entering `"combat"`, the system checks `initial.get("combat")` to resolve to a leaf (e.g., `"combat.defend"`). The `history` dict records the last active child so re-entering a parent resumes where it left off.

> **Gotcha:** When transitioning UP in the hierarchy (e.g., from `"combat.attack"` to `"idle"`), the system clears history for the target subtree. Without this, `_resolve_target` would chain through history and land right back in the branch being left, creating an infinite loop.

> **Gotcha:** `_resolve_target` uses a `seen` set to guard against cycles in history/initial chains. If your initial map creates a cycle, it won't infinite-loop -- it'll stop at the first revisited state.

### FSMGuards

```python
class FSMGuards:
    def register(self, name: str, fn: Callable[[World, EntityId], bool]) -> None
    def check(self, name: str, world: World, eid: EntityId) -> bool  # raises KeyError
    def has(self, name: str) -> bool
    def names(self) -> list[str]
```

### make_fsm_system

```python
def make_fsm_system(
    guards: FSMGuards,
    on_transition: Callable[[World, TickContext, EntityId, str, str], None] | None = None,
) -> Callable[[World, TickContext], None]
```
`on_transition(world, ctx, eid, old_state, new_state)` -- fires after each state change.

---

## tick-blueprint -- Entity Templates

`from tick_blueprint import BlueprintRegistry`

Define reusable entity templates (recipes) and spawn entities from them.

> **Why fully-qualified type keys:** Blueprint recipes use string keys like `"game.components.Position"` instead of direct type references. This keeps recipes serializable and avoids import-order issues. The trade-off is verbosity -- use `f"{ctype.__module__}.{ctype.__qualname__}"` to generate keys.

### At a Glance

| What | How |
|------|-----|
| Create registry | `reg = BlueprintRegistry()` |
| Define template | `reg.define("soldier", {"mod.Pos": {"x": 0}, "mod.Health": {"hp": 100}})` |
| Spawn from template | `eid = reg.spawn(world, "soldier", overrides={"mod.Pos": {"x": 5}})` |
| Add metadata | `reg.define("wall", recipe, meta={"cost": 10, "category": "defense"})` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `BlueprintRegistry` | class | Template storage and instantiation |

### BlueprintRegistry

```python
class BlueprintRegistry:
    def __init__(self) -> None
```

**Methods:**

```python
def define(self, name: str, recipe: dict[str, dict[str, Any]], meta: dict[str, Any] | None = None) -> None
```
Define a template. `recipe` maps component type keys to field dicts. Keys must match `f"{ctype.__module__}.{ctype.__qualname__}"`.

> **Gotcha:** Recipe keys are fully-qualified type names like `"game.components.Position"`, not simple class names. The type must be registered in `World._registry` before `spawn()` is called.

```python
def spawn(self, world: World, name: str, overrides: dict[str, dict[str, Any]] | None = None) -> EntityId
```
Create an entity from a template. `overrides` merges into the recipe fields.

```python
def has(self, name: str) -> bool
def meta(self, name: str) -> dict[str, Any]    # raises KeyError
def recipes(self) -> dict[str, dict[str, dict[str, Any]]]  # deep copy
def remove(self, name: str) -> None             # raises KeyError
```

---

## tick-signal -- Event Bus

`from tick_signal import SignalBus, make_signal_system`

In-process pub/sub with per-tick flush semantics. Signals published during a tick are delivered when the signal system flushes.

> **Why deferred delivery:** Systems that publish signals during a tick don't want handlers firing mid-system and changing the world out from under them. By queuing signals and flushing at a known point in the system order, you get predictable delivery timing. Place `make_signal_system(bus)` last in your system registration to flush after all systems have published.

> **Gotcha:** `make_signal_system` is NOT re-exported by tick-colony. Import it directly from `tick_signal`.

### At a Glance

| What | How |
|------|-----|
| Create bus | `bus = SignalBus()` |
| Subscribe | `bus.subscribe("damage", my_handler)` |
| Publish | `bus.publish("damage", target=eid, amount=10)` (queued) |
| Flush system | `engine.add_system(make_signal_system(bus))` (place last) |
| Handler signature | `(signal_name: str, data: dict[str, Any]) -> None` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `SignalBus` | class | Pub/sub message broker |
| `make_signal_system` | function | System factory that calls `bus.flush()` |

### SignalBus

```python
class SignalBus:
    def __init__(self) -> None
    def subscribe(self, signal_name: str, handler: Callable[[str, dict[str, Any]], None]) -> None
    def unsubscribe(self, signal_name: str, handler: Callable[[str, dict[str, Any]], None]) -> None
    def publish(self, signal_name: str, **data: Any) -> None  # queues, does not deliver
    def flush(self) -> None    # delivers all queued signals to subscribers
    def clear(self) -> None    # discards queued signals without delivering
```

Handler signature: `(signal_name: str, data: dict[str, Any]) -> None`.

### make_signal_system

```python
def make_signal_system(bus: SignalBus) -> Callable[[World, TickContext], None]
```
Returns a system that calls `bus.flush()` each tick. Place it in the system order where you want signal delivery to happen.

---

## tick-tween -- Value Interpolation

`from tick_tween import Tween, EASINGS, make_tween_system`

Smoothly interpolate a numeric field on a target component over time.

> **Gotcha:** Like BlueprintRegistry, the `target` field uses a fully-qualified type key (`f"{ctype.__module__}.{ctype.__qualname__}"`). The component must be registered in the world and attached to the entity.

> **See also:** [Timer](#timer) for count-based delays without interpolation. [EASINGS](#easings) for available easing curves.

### At a Glance

| What | How |
|------|-----|
| Tween a field | `world.attach(eid, Tween(target="mod.Opacity", field="value", start_val=0, end_val=1, duration=20))` |
| With easing | Set `easing="ease_in_out"` (options: `linear`, `ease_in`, `ease_out`, `ease_in_out`) |
| Create system | `engine.add_system(make_tween_system(on_complete=cb))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `Tween` | dataclass | Interpolation component |
| `EASINGS` | dict | Mapping of easing name to function |
| `make_tween_system` | function | System factory for processing tweens |

### Tween

```python
@dataclass
class Tween:
    target: str        # Component type key (fully-qualified, e.g. "module.ClassName")
    field: str         # Field name on the target component to interpolate
    start_val: float   # Starting value
    end_val: float     # Ending value
    duration: int      # Total ticks for interpolation
    elapsed: int = 0   # Current progress (auto-managed)
    easing: str = "linear"  # Easing function name (key in EASINGS)
```

> **Gotcha:** `target` uses the same fully-qualified type key as `BlueprintRegistry` recipes: `f"{ctype.__module__}.{ctype.__qualname__}"`. The component type must be registered in the world.

### EASINGS

```python
EASINGS: dict[str, Callable[[float], float]] = {
    "linear": linear,        # t
    "ease_in": ease_in,      # t^2
    "ease_out": ease_out,    # t*(2-t)
    "ease_in_out": ease_in_out,  # smooth S-curve
}
```

All easing functions accept `t` in [0, 1] and return a value in [0, 1].

### make_tween_system

```python
def make_tween_system(
    on_complete: Callable[[World, TickContext, EntityId, Tween], None] | None = None,
) -> Callable[[World, TickContext], None]
```

The tween is detached **before** `on_complete` fires (same pattern as Timer).

---

## tick-spatial -- Spatial Indexing & Pathfinding

`from tick_spatial import Coord, Pos2D, Pos3D, SpatialIndex, Grid2D, Grid3D, HexGrid, pathfind, make_spatial_cleanup_system`

Integer-coordinate spatial indexing with multiple grid types and A* pathfinding.

> **Why integer coordinates:** The spatial index uses `Coord = tuple[int, ...]` (integer tuples), not floats. This gives you exact grid positions for tile-based games. If you need sub-tile precision, use `KinematicBody.position` (float tuples) from tick-physics and convert to grid coords when interacting with the spatial index.

> **Why N-dimensional:** `Coord` is `tuple[int, ...]`, not `tuple[int, int]`. The same pathfinding algorithm works for 2D, 3D, and hex grids. Grid implementations provide the topology (neighbors, heuristic); algorithms are topology-agnostic.

### At a Glance

| What | How |
|------|-----|
| Create grid | `grid = Grid2D(width=50, height=50)` |
| Place entity | `grid.place(eid, (x, y))` |
| Move entity | `grid.move(eid, (nx, ny))` |
| Find neighbors | `grid.neighbors((5, 3))` returns `list[Coord]` |
| Radius query | `grid.in_radius((5, 3), 3)` returns `list[(eid, Coord)]` |
| A* pathfind | `pathfind(grid, start, goal, walkable=cellmap.passable)` |
| Cleanup dead | `engine.add_system(make_spatial_cleanup_system(grid))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `Coord` | type alias | `tuple[int, ...]` -- N-dimensional coordinate |
| `Pos2D` | dataclass | 2D position component (`x: float, y: float`) |
| `Pos3D` | dataclass | 3D position component (`x: float, y: float, z: float`) |
| `SpatialIndex` | protocol | Interface for all grid implementations |
| `Grid2D` | class | 2D grid with Chebyshev distance (8-directional) |
| `Grid3D` | class | 3D grid with Chebyshev distance (26-directional) |
| `HexGrid` | class | Hexagonal grid |
| `pathfind` | function | A* pathfinding over any `SpatialIndex` |
| `make_spatial_cleanup_system` | function | System that removes dead entities from a grid |

### SpatialIndex Protocol

All grid types implement this interface:

```python
class SpatialIndex(Protocol):
    def place(self, eid: int, coord: Coord) -> None
    def move(self, eid: int, coord: Coord) -> None
    def remove(self, eid: int) -> None
    def at(self, coord: Coord) -> frozenset[int]
    def position_of(self, eid: int) -> Coord | None
    def in_radius(self, coord: Coord, r: int) -> list[tuple[int, Coord]]
    def neighbors(self, coord: Coord) -> list[Coord]
    def heuristic(self, a: Coord, b: Coord) -> float
    def tracked_entities(self) -> frozenset[int]
    def rebuild(self, world: World) -> None
```

> **Gotcha:** `in_radius` returns `list[tuple[int, Coord]]` (eid, coord pairs), not `(eid, x, y)`. This is consistent across all dimensionalities. Destructure as `for eid, coord in grid.in_radius(center, 5):`.

> **Tip:** Use `tracked_entities()` (public) to get all entity IDs in the index. Never access `_entities` directly -- the underscore means it's internal and may change.

### Grid2D

```python
class Grid2D:
    def __init__(self, width: int, height: int) -> None
```
Bounded 2D grid. 8-directional neighbors (Chebyshev). `rebuild()` reads `Pos2D` components from the world.

| Property | Type |
|----------|------|
| `width` | `int` |
| `height` | `int` |

### pathfind

```python
def pathfind(
    index: SpatialIndex,
    start: Coord,
    goal: Coord,
    cost: Callable[[Coord, Coord], float] | None = None,
    walkable: Callable[[Coord], bool] | None = None,
) -> list[Coord] | None
```
A* pathfinding. Returns the path as a list of coordinates (including start and goal), or `None` if no path exists.

- `cost(from_coord, to_coord)` -- step cost function. Defaults to 1.0 per step.
- `walkable(coord)` -- returns `False` for impassable cells. If `None`, all cells are walkable.

> **Tip:** Plug in `CellMap` directly: `pathfind(grid, start, goal, walkable=cellmap.passable, cost=cellmap.move_cost)`. These method signatures were designed to compose.

> **Gotcha:** The A* implementation uses a closed set to avoid revisiting nodes. Without this, stale nodes in the priority queue cause redundant work and potential correctness issues on graphs with varying costs.

> **Gotcha:** `pathfind()` returns `None` for unreachable goals, not an empty list. An empty path would be ambiguous (start == goal returns `[start]`).

### make_spatial_cleanup_system

```python
def make_spatial_cleanup_system(index: SpatialIndex) -> Callable[[World, object], None]
```
Returns a system that removes dead entities from the spatial index each tick.

---

## tick-atlas -- Cell Property Maps

`from tick_atlas import CellDef, CellMap`

Sparse, dimension-agnostic cell property storage for terrain, movement costs, and custom properties.

> **Why sparse:** Most maps have a dominant terrain type (e.g., "grass"). Instead of storing "grass" for every cell, CellMap stores only cells that differ from the default. This makes large maps memory-efficient. The trade-off is that `matches()` returns `False` for unset (default) cells -- see the gotcha below.

### At a Glance

| What | How |
|------|-----|
| Define cell type | `grass = CellDef("grass", passable=True, move_cost=1.0)` |
| Create map | `cm = CellMap(default=grass)` |
| Set cell | `cm.set((5, 3), wall)` |
| Check passable | `cm.passable((5, 3))` -- plugs into `pathfind(walkable=...)` |
| Get move cost | `cm.move_cost(from_c, to_c)` -- plugs into `pathfind(cost=...)` |
| Find by type | `cm.of_type("wall")` returns `list[Coord]` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `CellDef` | frozen dataclass | Immutable cell type definition |
| `CellMap` | class | Coordinate-to-cell-type mapping |

### CellDef

```python
@dataclass(frozen=True)
class CellDef:
    name: str                             # Unique identifier
    passable: bool = True                 # Can entities traverse this cell?
    move_cost: float = 1.0                # Pathfinding edge weight (>= 0)
    properties: dict[str, Any] = {}       # Arbitrary user data
```

### CellMap

```python
class CellMap:
    def __init__(self, default: CellDef) -> None
```
Sparse storage. Unset coordinates return the `default` CellDef.

| Property | Type | Description |
|----------|------|-------------|
| `default` | `CellDef` | Default cell type for unset coordinates |

**Registration and mutation:**

```python
def register(self, cell_def: CellDef) -> None    # Register for snapshot/restore
def set(self, coord: Coord, cell_def: CellDef) -> None
def clear(self, coord: Coord) -> None             # Reset to default
def clear_all(self) -> None
```

> **Gotcha:** `set()` with the default CellDef removes from storage (sparse optimization). If you need `matches()` to return `True` for a coord, you must explicitly set it to a non-default CellDef. For visible map areas, consider using a "void" default and explicitly setting all cells, even the common terrain type.

> **Gotcha:** `register()` registers a CellDef for snapshot/restore *without* setting any cell. You need this after restore so the CellMap can reconstruct cells from their names.

**Queries:**

```python
def at(self, coord: Coord) -> CellDef
def passable(self, coord: Coord) -> bool          # Matches pathfind(walkable=...) signature
def move_cost(self, from_coord: Coord, to_coord: Coord) -> float  # Matches pathfind(cost=...)
def matches(self, coord: Coord, requirements: dict[str, Any]) -> bool
def of_type(self, name: str) -> list[Coord]
def coords(self) -> list[Coord]                    # All non-default coordinates
```

`matches()` returns `False` for default (sparse) cells. The `"terrain"` key compares against `cell_def.name`; other keys compare against `cell_def.properties`.

**Bulk operations:**

```python
def fill(self, coords: list[Coord], cell_def: CellDef) -> None
def fill_rect(self, corner1: tuple[int, int], corner2: tuple[int, int], cell_def: CellDef) -> None
```

**Snapshot/Restore:**

```python
def snapshot(self) -> dict[str, Any]
def restore(self, data: dict[str, Any]) -> None    # All CellDefs must be registered first
```

---

## tick-physics -- Kinematics & Collisions

`from tick_physics import KinematicBody, CircleCollider, AABBCollider, Collision, vec, make_physics_system, make_collision_system`

N-dimensional physics: semi-implicit Euler integration, circle and AABB collision detection.

> **Why semi-implicit Euler:** The physics system updates velocity from forces first, then updates position from the new velocity. This is more stable than explicit Euler (which uses the old velocity for position) and is sufficient for most game-like simulations. It's not as accurate as Verlet or RK4, but it's simpler and cheaper.

> **Why N-dimensional:** All vec functions and collision detection work with tuples of any length. The same code handles 2D and 3D. You don't need separate physics libraries for different dimensionalities.

### At a Glance

| What | How |
|------|-----|
| Add body | `world.attach(eid, KinematicBody(position=(0,0), velocity=(1,0)))` |
| Add circle collider | `world.attach(eid, CircleCollider(radius=5.0))` |
| Add AABB collider | `world.attach(eid, AABBCollider(half_extents=(2.0, 3.0)))` |
| Apply force | `body.forces.append((0.0, -9.8 * body.mass))` |
| Run physics | `engine.add_system(make_physics_system())` |
| Detect collisions | `engine.add_system(make_collision_system(on_collision=cb))` |
| Vector math | `vec.add(a, b)`, `vec.normalize(v)`, `vec.distance(a, b)` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `KinematicBody` | dataclass | Position, velocity, mass, force accumulator |
| `CircleCollider` | dataclass | Circle/sphere collision shape |
| `AABBCollider` | dataclass | Axis-aligned bounding box collision shape |
| `Collision` | frozen dataclass | Collision info (not a component) |
| `vec` | module | N-dimensional vector math functions |
| `make_physics_system` | function | Semi-implicit Euler integrator |
| `make_collision_system` | function | O(n^2) collision detection |

### Components

```python
@dataclass
class KinematicBody:
    position: tuple[float, ...]          # N-dimensional position
    velocity: tuple[float, ...]          # N-dimensional velocity
    mass: float = 1.0
    forces: list[tuple[float, ...]] = [] # Accumulated forces (cleared each tick)

@dataclass
class CircleCollider:
    radius: float                        # Center = KinematicBody.position

@dataclass
class AABBCollider:
    half_extents: tuple[float, ...]      # Half-size from center (KinematicBody.position)

@dataclass(frozen=True)
class Collision:
    entity_a: int
    entity_b: int
    normal: tuple[float, ...]            # Direction from A toward B
    depth: float                         # Penetration depth
```

`Collision` is passed to callbacks -- it is NOT a component and should not be attached to entities.

> **Why Collision is not a component:** Collisions are transient events, not persistent state. A collision exists for a single callback invocation, not for the lifetime of an entity. Making it frozen prevents accidental mutation.

> **Gotcha:** `KinematicBody.forces` defaults to `[]` (mutable default). In practice this is fine because the physics system clears forces every tick, but be aware that `dataclasses.field(default_factory=list)` would be "safer". The current design trades pedantry for convenience.

### vec Module

Pure functions operating on `Vec = tuple[float, ...]`:

| Function | Signature | Description |
|----------|-----------|-------------|
| `add(a, b)` | `(Vec, Vec) -> Vec` | Element-wise addition |
| `sub(a, b)` | `(Vec, Vec) -> Vec` | Element-wise subtraction |
| `scale(v, s)` | `(Vec, float) -> Vec` | Scalar multiplication |
| `dot(a, b)` | `(Vec, Vec) -> float` | Dot product |
| `magnitude(v)` | `(Vec,) -> float` | Length / L2 norm |
| `magnitude_sq(v)` | `(Vec,) -> float` | Squared magnitude (avoids sqrt) |
| `normalize(v)` | `(Vec,) -> Vec` | Unit vector (returns `v` unchanged if zero) |
| `distance(a, b)` | `(Vec, Vec) -> float` | Euclidean distance |
| `distance_sq(a, b)` | `(Vec, Vec) -> float` | Squared distance |
| `zero(dimensions)` | `(int,) -> Vec` | Zero vector of given dimensionality |
| `clamp_magnitude(v, max)` | `(Vec, float) -> Vec` | Clamp vector length |

All functions work with any dimensionality. 2D and 3D use the same code.

### System Factories

```python
def make_physics_system() -> Callable[[World, TickContext], None]
```
Semi-implicit Euler: forces -> velocity -> position. Forces cleared after each tick. Entities with no forces still move (velocity persists).

> **Tip:** To apply gravity, append a force each tick: `body.forces.append((0.0, -9.8 * body.mass))`. Forces are accumulated and applied collectively, then cleared. Don't set velocity directly unless you want to override physics (e.g., teleportation).

```python
def make_collision_system(
    on_collision: Callable[[World, TickContext, Collision], None],
) -> Callable[[World, TickContext], None]
```
O(n^2) broadphase. Detects circle-circle, AABB-AABB, and circle-AABB overlaps. Calls `on_collision` for each detected pair. The callback decides what to do (bounce, damage, ignore).

> **Why O(n^2):** This is deliberately simple. For most tick-engine simulations (dozens to low hundreds of entities), O(n^2) is fast enough. Spatial hash optimization is planned for v0.2.0 but was deferred to avoid premature complexity.

> **Gotcha:** The collision `normal` points from entity_a toward entity_b. For circle-vs-AABB, the internal detection computes the normal from circle center toward the closest point on the AABB, then flips it if the AABB is entity_a. This ensures the normal always goes A->B regardless of shape combination.

> **Gotcha:** The collision system uses `AnyOf(CircleCollider, AABBCollider)` in its query, then uses `world.has()`/`world.get()` to determine the actual shape type. An entity with BOTH colliders will be treated as whichever is checked first (circle takes priority).

> **See also:** [vec module](#vec-module) for the math primitives used in collision resolution. [make_spatial_cleanup_system](#make_spatial_cleanup_system) for removing dead entities from the grid after despawn.

---

## tick-event -- World-Level Event Scheduling

`from tick_event import EventDef, ActiveEvent, CycleDef, CycleState, EventGuards, EventScheduler, make_event_system`

Global events (e.g., weather, seasons, raids) with probability, conditions, cooldowns, and repeating phase cycles.

> **Why world-level:** Unlike components (per-entity), these events affect the entire simulation. A "winter" event doesn't belong on any single entity -- it's a global state that systems can query via `scheduler.is_active("winter")`.

> **See also:** [SignalBus](#signalbus) for entity-level pub/sub. [AbilityManager](#abilitymanager) for entity-level ability-like effects with cooldowns. EventScheduler is the global-scope equivalent.

### At a Glance

| What | How |
|------|-----|
| Define event | `scheduler.define(EventDef("raid", duration=50, cooldown=200, probability=0.3))` |
| Define cycle | `scheduler.define_cycle(CycleDef("seasons", [("spring",100),("summer",100),...]))` |
| Check active | `scheduler.is_active("raid")` |
| Create system | `engine.add_system(make_event_system(scheduler, guards, on_start=cb))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `EventDef` | dataclass | Event definition (not serialized) |
| `ActiveEvent` | dataclass | Runtime state of a running event |
| `CycleDef` | dataclass | Repeating phase cycle definition |
| `CycleState` | dataclass | Runtime state of a cycle |
| `EventGuards` | class | Guard predicate registry |
| `EventScheduler` | class | Event manager with snapshot/restore |
| `make_event_system` | function | System factory |

### EventDef

```python
@dataclass
class EventDef:
    name: str
    duration: int | tuple[int, int]      # Fixed ticks or (min, max) random range
    cooldown: int = 0                     # Min ticks before re-fire
    probability: float = 1.0             # Per-evaluation chance [0.0, 1.0]
    conditions: list[str] = []           # Guard names, ALL must pass
```

### CycleDef

```python
@dataclass
class CycleDef:
    name: str
    phases: list[tuple[str, int]]        # [(phase_name, duration_ticks), ...]
    delay: int = 0                        # Ticks before first phase
```

### EventScheduler

```python
class EventScheduler:
    def __init__(self) -> None
    def define(self, event: EventDef) -> None
    def define_cycle(self, cycle: CycleDef) -> None
    def is_active(self, name: str) -> bool
    def active_events(self) -> list[ActiveEvent]
    def time_remaining(self, name: str) -> int
    def definition(self, name: str) -> EventDef | None
    def snapshot(self) -> dict[str, Any]
    def restore(self, data: dict[str, Any]) -> None  # Re-register definitions first
```

### EventGuards

```python
class EventGuards:
    def register(self, name: str, fn: Callable[[World, EventScheduler], bool]) -> None
    def check(self, name: str, world: World, scheduler: EventScheduler) -> bool
    def has(self, name: str) -> bool
    def names(self) -> list[str]
```

### make_event_system

```python
def make_event_system(
    scheduler: EventScheduler,
    guards: EventGuards,
    on_start: Callable[[World, TickContext, str], None] | None = None,
    on_end: Callable[[World, TickContext, str], None] | None = None,
    on_tick: Callable[[World, TickContext, str, int], None] | None = None,
) -> Callable[[World, TickContext], None]
```

Callback parameter labels:
- `on_start(world, ctx, event_name)` — fires when an event activates
- `on_end(world, ctx, event_name)` — fires when an event expires (also on cycle phase transitions)
- `on_tick(world, ctx, event_name, remaining_ticks)` — fires each tick while active

Tick execution order:
1. Decrement active events, end expired ones (`on_end`)
2. Tick still-active events (`on_tick` with remaining ticks)
3. Process cycles -- advance phases (`on_end` for old, `on_start` for new)
4. Decrement cooldowns
5. Evaluate inactive events -- check guards, roll probability, activate (`on_start`)

---

## tick-ability -- Player-Triggered Abilities

`from tick_ability import AbilityDef, AbilityState, AbilityGuards, AbilityManager, make_ability_system`

Abilities with charges, cooldowns, duration, and guard conditions.

> **Why a separate package:** Abilities have a distinct lifecycle (invoke -> active -> cooldown -> available) that's more complex than a simple timer. They also have charges, guard conditions, and the ability to be queried for availability. This warranted a dedicated package rather than overloading tick-schedule.

### At a Glance

| What | How |
|------|-----|
| Define ability | `mgr.define(AbilityDef("fireball", duration=3, cooldown=10, max_charges=2))` |
| Invoke ability | `mgr.invoke("fireball", world, ctx, guards)` returns `bool` |
| Check available | `mgr.is_available("fireball", world, guards)` |
| Check active | `mgr.is_active("fireball")` |
| Create system | `engine.add_system(make_ability_system(mgr, guards, on_start=cb))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `AbilityDef` | dataclass | Ability definition (not serialized) |
| `AbilityState` | dataclass | Runtime state (serializable) |
| `AbilityGuards` | class | Guard predicate registry |
| `AbilityManager` | class | Ability lifecycle manager |
| `make_ability_system` | function | System factory |

### AbilityDef

```python
@dataclass
class AbilityDef:
    name: str
    duration: int | tuple[int, int]      # Fixed ticks or (min, max) random range
    cooldown: int = 0                     # Ticks after effect ends before re-use
    max_charges: int = 1                 # -1 for unlimited
    charge_regen: int = 0                # Ticks between charge regeneration (0 = no regen)
    conditions: list[str] = []           # Guard names, ALL must pass
```

### AbilityManager

```python
class AbilityManager:
    def __init__(self) -> None
    def define(self, ability: AbilityDef) -> None
    def definition(self, name: str) -> AbilityDef | None
    def invoke(self, name: str, world: World, ctx: TickContext, guards: AbilityGuards | None = None) -> bool
    def is_available(self, name: str, world: World, guards: AbilityGuards | None = None) -> bool
    def is_active(self, name: str) -> bool
    def charges(self, name: str) -> int           # -1 for unlimited; raises KeyError
    def time_remaining(self, name: str) -> int    # raises KeyError
    def cooldown_remaining(self, name: str) -> int # raises KeyError
    def state(self, name: str) -> AbilityState | None
    def defined_abilities(self) -> list[str]
    def snapshot(self) -> dict[str, Any]
    def restore(self, data: dict[str, Any]) -> None  # Re-register definitions first
```

> **Gotcha:** `invoke()` checks `active_started_at != -1` to block re-invocation of instantaneous (duration=0) abilities on the same tick. Without this check, a duration-0 ability could be invoked, processed, and invoked again in the same tick.

> **Gotcha:** The ability system processes abilities on the SAME tick as invoke if `invoke_system` runs before `ability_system` in your system registration order. This means `on_start` fires the same tick as `invoke()` -- which is usually what you want for responsiveness.

> **Gotcha:** `AbilityManager` definitions are NOT serialized. The runtime state (charges, cooldowns) IS serialized via `snapshot()`/`restore()`. Re-register all `AbilityDef`s before calling `restore()`.

> **See also:** [EventScheduler](#eventscheduler) for global-scope events with similar cooldown mechanics. [Timer](#timer) for simpler one-shot delays without the ability lifecycle.

### AbilityGuards

```python
class AbilityGuards:
    def register(self, name: str, fn: Callable[[World, AbilityManager], bool]) -> None
    def check(self, name: str, world: World, manager: AbilityManager) -> bool
    def has(self, name: str) -> bool
    def names(self) -> list[str]
```

### make_ability_system

```python
def make_ability_system(
    manager: AbilityManager,
    guards: AbilityGuards | None = None,
    on_start: Callable[[World, TickContext, str], None] | None = None,
    on_end: Callable[[World, TickContext, str], None] | None = None,
    on_tick: Callable[[World, TickContext, str, int], None] | None = None,
) -> Callable[[World, TickContext], None]
```

Tick execution order:
1. Process newly-invoked abilities (`on_start`; instantaneous get `on_end` too)
2. Decrement active effects -- end expired ones (`on_end`)
3. Tick still-active effects (`on_tick`)
4. Decrement cooldowns
5. Regenerate charges

---

## tick-command -- Typed Command Queue

`from tick_command import CommandQueue, make_command_system, expand_footprint, resolve_footprint`

External commands flow through a FIFO queue to typed handlers inside the tick loop.

> **Why a command queue:** In a game, input (mouse clicks, keyboard, network) arrives asynchronously, but the simulation runs at a fixed tick rate. The command queue bridges this gap: `enqueue()` from any thread or context, `drain()` inside the tick loop. This prevents race conditions and ensures all commands are processed in a deterministic order.

> **Tip:** Place the command system first in your system registration order so that player actions take effect before AI, physics, etc. process the current tick.

### At a Glance

| What | How |
|------|-----|
| Create queue | `q = CommandQueue()` |
| Register handler | `q.handle(BuildCmd, lambda cmd, w, ctx: True)` |
| Enqueue command | `q.enqueue(BuildCmd(x=5, y=3))` (safe from any thread) |
| Create system | `engine.add_system(make_command_system(q, on_accept=cb))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `CommandQueue` | class | FIFO command queue with typed dispatch |
| `make_command_system` | function | System factory that drains the queue |
| `expand_footprint` | function | Expand rectangular footprint to coordinates |
| `resolve_footprint` | function | Normalize dimensions or offsets to coordinates |

### CommandQueue

```python
class CommandQueue:
    def __init__(self) -> None
    def handle(self, cmd_type: type, handler: Callable[..., bool]) -> None
    def enqueue(self, cmd: Any) -> None
    def pending(self) -> int
    def drain(self, world: World, ctx: TickContext) -> list[tuple[Any, bool]]
```

- `handle(cmd_type, handler)` -- `handler(cmd, world, ctx) -> bool`. Return `True` to accept, `False` to reject. One handler per type.
- `enqueue(cmd)` -- Safe to call from outside the tick loop (e.g., from UI/input handlers).
- `drain()` -- Process all pending commands. Raises `TypeError` if no handler for a command's type.

Commands should be frozen dataclasses. The engine imposes no base class.

### make_command_system

```python
def make_command_system(
    queue: CommandQueue,
    on_accept: Callable[[Any], None] | None = None,
    on_reject: Callable[[Any], None] | None = None,
) -> Callable[[World, TickContext], None]
```

### Footprint Utilities

```python
def expand_footprint(origin: Coord, dimensions: tuple[int, ...]) -> list[Coord]
```
Expand a rectangular region from `origin` with `dimensions`. E.g., `expand_footprint((5, 3), (2, 2))` returns `[(5,3), (5,4), (6,3), (6,4)]`.

```python
def resolve_footprint(origin: Coord, shape: tuple[int, ...] | list[Coord]) -> list[Coord]
```
Normalize either a dimensions tuple or a list of relative offsets to absolute coordinates.

---

## tick-resource -- Inventories & Crafting

`from tick_resource import Inventory, InventoryHelper, Recipe, ResourceDef, ResourceRegistry, can_craft, craft, make_resource_decay_system`

Resource management with inventories, crafting recipes, type definitions, and decay.

> **Why string-based resources:** Resources are identified by name strings, not types. This means you can define new resources at runtime (e.g., from data files or LLM output) without creating new Python classes. `ResourceRegistry` is optional -- `Inventory` works standalone with just string names and integer quantities.

### At a Glance

| What | How |
|------|-----|
| Add inventory | `world.attach(eid, Inventory(capacity=100))` |
| Add resources | `InventoryHelper.add(inv, "wood", 10)` returns amount added |
| Check stock | `InventoryHelper.has(inv, "wood", 5)` |
| Craft item | `craft(inv, Recipe("axe", inputs={"wood":2,"iron":1}, outputs={"axe":1}))` |
| Transfer between | `InventoryHelper.transfer(source_inv, target_inv, "wood", 5)` |
| Decay system | `engine.add_system(make_resource_decay_system(registry, on_spoiled=cb))` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `Inventory` | dataclass | Resource storage component |
| `InventoryHelper` | class | Static methods for inventory manipulation |
| `Recipe` | frozen dataclass | Crafting recipe |
| `ResourceDef` | frozen dataclass | Resource type definition |
| `ResourceRegistry` | class | Resource type registry |
| `can_craft` | function | Check if inventory has recipe inputs |
| `craft` | function | Consume inputs and produce outputs |
| `make_resource_decay_system` | function | System factory for decay |

### Inventory

```python
@dataclass
class Inventory:
    slots: dict[str, int] = {}     # resource_name -> quantity
    capacity: int = -1              # Max total quantity (-1 = unlimited)
```

> **Gotcha:** Empty slots are deleted (key removed when quantity reaches 0). Don't access `inv.slots[name]` directly -- use `InventoryHelper.count()` or `inv.slots.get(name, 0)`.

### InventoryHelper

All methods are `@staticmethod`:

| Method | Signature | Description |
|--------|-----------|-------------|
| `add(inv, name, amount=1)` | `-> int` | Add resources, respecting capacity. Returns amount added |
| `remove(inv, name, amount=1)` | `-> int` | Remove resources. Returns amount removed |
| `count(inv, name)` | `-> int` | Current quantity |
| `total(inv)` | `-> int` | Total across all types |
| `has(inv, name, amount=1)` | `-> bool` | Check if at least `amount` exists |
| `has_all(inv, requirements)` | `-> bool` | Check all `{name: qty}` requirements |
| `transfer(source, target, name, amount=1)` | `-> int` | Move between inventories. Returns transferred |
| `names(inv)` | `-> list[str]` | All resource types currently held |
| `clear(inv, name=None)` | `-> None` | Clear one type or everything |

### Recipe

```python
@dataclass(frozen=True)
class Recipe:
    name: str
    inputs: dict[str, int] = {}      # resource_name -> quantity needed
    outputs: dict[str, int] = {}     # resource_name -> quantity produced
    duration: int = 0                 # Ticks to complete (metadata only)
```

```python
def can_craft(inventory: Inventory, recipe: Recipe) -> bool
def craft(inventory: Inventory, recipe: Recipe) -> bool   # Returns False if insufficient
```

### ResourceDef

```python
@dataclass(frozen=True)
class ResourceDef:
    name: str
    max_stack: int = -1              # Max per slot (-1 = unlimited)
    properties: dict[str, Any] = {}  # Arbitrary metadata
    decay_rate: int = 0              # Units lost per tick (0 = no decay)
```

### ResourceRegistry

```python
class ResourceRegistry:
    def __init__(self) -> None
    def define(self, resource_def: ResourceDef) -> None
    def get(self, name: str) -> ResourceDef            # raises KeyError
    def has(self, name: str) -> bool
    def defined_resources(self) -> list[str]
    def remove(self, name: str) -> None                # raises KeyError
    def snapshot(self) -> dict[str, Any]
    def restore(self, data: dict[str, Any]) -> None
```

### make_resource_decay_system

```python
def make_resource_decay_system(
    registry: ResourceRegistry,
    on_spoiled: Callable[..., None] | None = None,
) -> Callable[..., None]
```
`on_spoiled(world, ctx, entity_id, resource_name, amount_lost)` -- fires when resources decay.

---

## tick-ai -- Behavior Trees & Utility AI

`from tick_ai import AIManager, Status, BehaviorTree, Blackboard, UtilityAgent, Node, curves, make_bt_system, make_utility_system`

Behavior trees with 10 node types, utility AI with multiplicative scoring, and a shared blackboard.

> **Why both BT and utility AI:** Behavior trees excel at sequential, priority-based decision making ("if enemy near, fight; else patrol"). Utility AI excels at continuous trade-off evaluation ("what's the most valuable thing to do right now?"). Many games use both: BTs for structured behavior, utility for action selection within BT leaves.

> **Why a flat Node union:** All 10 node types are frozen dataclasses in a flat `Node` type union rather than a class hierarchy. This makes them hashable, serializable, and easy to construct declaratively from data. The evaluator dispatches by `isinstance` checks.

### At a Glance

| What | How |
|------|-----|
| Create manager | `mgr = AIManager()` |
| Register action | `mgr.register_action("chase", lambda w, ctx, eid: Status.SUCCESS)` |
| Register condition | `mgr.register_condition("enemy_near", lambda w, eid: True)` |
| Define tree | `mgr.define_tree("patrol", root_id="root", nodes={...})` |
| Attach BT to entity | `world.attach(eid, BehaviorTree(tree_name="patrol"))` |
| Attach blackboard | `world.attach(eid, Blackboard(data={}))` |
| Run BT system | `engine.add_system(make_bt_system(mgr, on_status=cb))` |
| Utility scoring | `mgr.define_utility_action("forage", ["hunger", "safety"])` |
| Run utility system | `engine.add_system(make_utility_system(mgr, on_select=cb))` |
| Response curves | `curves.linear`, `curves.logistic`, `curves.step` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `AIManager` | class | Central registry for trees, actions, conditions, utility |
| `Status` | enum | `SUCCESS`, `FAILURE`, `RUNNING` |
| `BehaviorTree` | dataclass | Entity component: assigns a BT |
| `Blackboard` | dataclass | Entity component: per-entity key-value store |
| `UtilityAgent` | dataclass | Entity component: assigns a utility selector |
| `Action` | frozen dataclass | Leaf node: calls registered action |
| `Condition` | frozen dataclass | Leaf node: calls registered guard |
| `Sequence` | frozen dataclass | Composite: all children must succeed |
| `Selector` | frozen dataclass | Composite: first success wins |
| `Parallel` | frozen dataclass | Composite: runs all children every tick |
| `UtilitySelector` | frozen dataclass | Composite: scores children via utility |
| `Inverter` | frozen dataclass | Decorator: flips SUCCESS/FAILURE |
| `Repeater` | frozen dataclass | Decorator: repeats child N times |
| `Succeeder` | frozen dataclass | Decorator: always SUCCESS |
| `AlwaysFail` | frozen dataclass | Decorator: always FAILURE |
| `Node` | type alias | Union of all 10 node types |
| `curves` | module | Response curves for utility considerations |
| `make_bt_system` | function | System factory for behavior trees |
| `make_utility_system` | function | System factory for utility AI |

### Node Types

**Leaf nodes:**

```python
Action(id: str, action: str)           # Calls manager.action(action_name)
Condition(id: str, condition: str)     # Calls manager.condition(condition_name)
```

**Composite nodes:**

```python
Sequence(id: str, children: tuple[str, ...])    # All must succeed; fails on first failure
Selector(id: str, children: tuple[str, ...])    # First success wins; fallback chain
Parallel(id: str, children: tuple[str, ...], policy: str = "require_all")
UtilitySelector(id: str, children: tuple[str, ...])
```

`Parallel` policies: `"require_all"` (success when all succeed, fail when any fails) or `"require_one"` (success when any succeeds).

**Decorator nodes:**

```python
Inverter(id: str, child: str)
Repeater(id: str, child: str, max_count: int = 1, fail_policy: str = "fail")
Succeeder(id: str, child: str)
AlwaysFail(id: str, child: str)
```

`Repeater.fail_policy`: `"fail"` (propagate FAILURE) or `"restart"` (keep going).

### Components

```python
@dataclass
class BehaviorTree:
    tree_name: str                        # Name of tree definition in AIManager
    running_node: str = ""                # ID of currently-running node (auto-managed)
    status: str = ""                      # Last result: "success", "failure", ""
    repeat_counts: dict[str, int] = {}    # Repeater state (auto-managed)

@dataclass
class Blackboard:
    data: dict[str, Any] = {}             # Per-entity key-value knowledge store

@dataclass
class UtilityAgent:
    selector_name: str                    # Name of utility selector in AIManager
    selected_action: str = ""             # Last selected action (auto-managed)
    score: float = 0.0                    # Score of selected action
```

### AIManager

```python
class AIManager:
    def __init__(self) -> None

    # Tree definitions
    def define_tree(self, name: str, root_id: str, nodes: dict[str, Node]) -> None
    def tree(self, name: str) -> tuple[str, dict[str, Node]] | None

    # Callbacks
    def register_action(self, name: str, fn: Callable[[World, TickContext, int], Status]) -> None
    def register_condition(self, name: str, fn: Callable[[World, int], bool]) -> None
    def register_consideration(self, name: str, fn: Callable[[World, int], float]) -> None

    # Lookups
    def action(self, name: str) -> ActionFn | None
    def condition(self, name: str) -> ConditionFn | None
    def consideration(self, name: str) -> ConsiderationFn | None

    # Utility AI
    def define_utility_action(self, action_name: str, considerations: list[str]) -> None
    def define_utility_selector(self, name: str, action_names: list[str]) -> None
    def score_action(self, action_name: str, world: World, eid: int) -> float
    def select_action(self, selector_name: str, world: World, eid: int) -> tuple[str, float]
    def utility_selector(self, name: str) -> list[str] | None
```

`define_tree()` validates the node graph (root exists, child refs valid, id matches key). Validation catches orphan nodes and broken references at definition time, not at runtime.

Callback signatures:
- **Action:** `(World, TickContext, int) -> Status` -- the `int` is the entity ID
- **Condition:** `(World, int) -> bool` -- no TickContext (conditions should be stateless queries)
- **Consideration:** `(World, int) -> float` (clamped to [0.0, 1.0])

> **Why no TickContext in conditions:** Conditions are pure queries ("is enemy nearby?"), not behaviors. They don't need dt or elapsed time. Actions get TickContext because they may perform work that depends on time.

> **Gotcha:** Register all considerations with `register_consideration()` **before** calling `define_utility_action()`. The action definition stores consideration names; if they're not registered when scoring runs, the score defaults to 0.0.

> **Gotcha:** Utility scoring is multiplicative across considerations. A single 0.0 consideration short-circuits the entire action to 0.0. This is by design -- it models hard requirements (if hunger is 0, foraging has zero utility). Use `curves.step()` to create binary gates.

> **Gotcha:** AIManager is NOT serialized. Definitions are code-only -- re-register all trees, actions, conditions, and considerations after restore. The `BehaviorTree` component (tree_name, running_node, status, repeat_counts) IS serialized -- it's all the per-entity runtime state.

> **Tip:** RUNNING resumption uses ancestry tracking. When a tree has a RUNNING node from the previous tick, composite nodes (Sequence, Selector) skip children before the running child's ancestor. This means a Sequence won't re-run already-succeeded children when resuming. Parallel is the exception -- it runs ALL children every tick regardless.

> **See also:** [tick-llm](#tick-llm---async-llm-strategic-layer) builds on tick-ai's Blackboard for LLM-driven strategic decision making. [curves module](#curves-module) for shaping utility consideration responses.

### curves Module

Response curves for utility AI. All accept `x` in [0, 1], return in [0, 1]. Input is clamped.

| Function | Signature | Description |
|----------|-----------|-------------|
| `linear(x, m=1.0, b=0.0)` | `-> float` | `y = m*x + b` |
| `quadratic(x, exp=2.0)` | `-> float` | `y = x^exp` |
| `logistic(x, k=10.0, midpoint=0.5)` | `-> float` | Sigmoid / S-curve |
| `inverse(x, steepness=1.0)` | `-> float` | `y = 1 - x^steepness` |
| `step(x, threshold=0.5)` | `-> float` | 0 below threshold, 1 at or above |

### System Factories

```python
def make_bt_system(
    manager: AIManager,
    on_status: Callable[[World, TickContext, int, str], None] | None = None,
) -> Callable[[World, TickContext], None]
```
`on_status(world, ctx, eid, status_value)` -- fired when a tree completes (SUCCESS or FAILURE, not RUNNING).

```python
def make_utility_system(
    manager: AIManager,
    on_select: Callable[[World, TickContext, int, str, float], None] | None = None,
) -> Callable[[World, TickContext], None]
```
`on_select(world, ctx, eid, action_name, score)` -- fired after each selection.

---

## tick-llm -- Async LLM Strategic Layer

`from tick_llm import LLMAgent, LLMClient, LLMConfig, LLMManager, LLMSystem, MockClient, ContextFn, ParserFn, default_json_parser, strip_code_fences, make_llm_system`

Asynchronous LLM queries integrated into the tick loop via a thread pool. Handles rate limiting, timeouts, error recovery, and cooldowns.

> **Why async in a sync engine:** LLM queries take 1-30 seconds. You cannot block a 20-TPS tick loop waiting for a response. tick-llm submits queries to a ThreadPoolExecutor and harvests results on subsequent ticks. The entity keeps ticking normally while its query is in flight. The `pending` flag prevents duplicate submissions.

> **Why thread pool, not asyncio:** The tick engine is synchronous by design. Introducing asyncio would require every system to be async-aware. A thread pool is the simplest bridge between sync tick processing and blocking I/O calls.

### At a Glance

| What | How |
|------|-----|
| Create manager | `mgr = LLMManager(LLMConfig(max_queries_per_tick=2))` |
| Register client | `mgr.register_client(my_client)` |
| Define role | `mgr.define_role("strategist", "You are a colony strategist...")` |
| Define context | `mgr.define_context("colony", make_colony_context(...))` |
| Attach agent | `world.attach(eid, LLMAgent(role="strategist", personality="cautious", context="colony"))` |
| Run LLM system | `llm_sys = make_llm_system(mgr); engine.add_system(llm_sys)` |
| Shutdown on stop | `engine.on_stop(lambda w, c: llm_sys.shutdown())` |
| Test with mock | `MockClient(responses={("sys", "usr"): '{"action":"wait"}'})` |

### Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `LLMAgent` | dataclass | Entity component marking LLM-driven entities |
| `LLMClient` | protocol | Interface for LLM implementations |
| `LLMConfig` | frozen dataclass | Rate limits and thread pool configuration |
| `LLMManager` | class | Central registry for prompt components |
| `LLMSystem` | class | Async query system (callable as a tick system) |
| `MockClient` | class | Deterministic test client |
| `ContextFn` | type alias | `Callable[[World, int], str]` |
| `ParserFn` | type alias | `Callable[[str, Blackboard], None]` |
| `default_json_parser` | function | Strip fences, parse JSON, merge into blackboard |
| `strip_code_fences` | function | Remove markdown code fences |
| `make_llm_system` | function | Factory for `LLMSystem` |

### LLMAgent

```python
@dataclass
class LLMAgent:
    role: str                    # Role definition name in LLMManager
    personality: str             # Personality definition name
    context: str                 # Context template name
    parser: str = ""             # Parser name (empty = default JSON parser)
    query_interval: int = 100    # Min ticks between queries
    priority: int = 0            # Higher = queried first
    last_query_tick: int = 0     # Auto-managed
    pending: bool = False        # True while query in flight
    consecutive_errors: int = 0  # Auto-managed
    max_retries: int = 3         # Errors before cooldown
    cooldown_ticks: int = 200    # Cooldown duration
    cooldown_until: int = 0      # Tick when cooldown expires
```

### LLMClient Protocol

```python
@runtime_checkable
class LLMClient(Protocol):
    def query(self, system_prompt: str, user_message: str) -> str: ...
```
Blocking call. Invoked inside a thread pool worker. Any exception triggers error handling.

> **Tip:** Implement this protocol for your LLM backend (OpenAI, Anthropic, local LM Studio, etc.). The system handles threading, timeouts, and retries -- your client just needs to make a blocking HTTP call and return the response text.

### MockClient

```python
class MockClient:
    def __init__(
        self,
        responses: dict[tuple[str, str], str] | Callable[[str, str], str],
        latency: float = 0.0,
        error_rate: float = 0.0,
        error_exception: BaseException | None = None,
    ) -> None
```
For testing. Thread-safe via per-instance RNG.

### LLMConfig

```python
@dataclass(frozen=True)
class LLMConfig:
    max_queries_per_tick: int = 1
    max_queries_per_second: int = 5
    thread_pool_size: int = 4
    query_timeout: float = 30.0
```

### LLMManager

```python
class LLMManager:
    def __init__(self, config: LLMConfig | None = None) -> None

    # Definitions
    def define_role(self, name: str, text: str) -> None
    def define_personality(self, name: str, text: str) -> None
    def define_context(self, name: str, fn: ContextFn) -> None
    def define_parser(self, name: str, fn: ParserFn) -> None
    def register_client(self, client: LLMClient) -> None

    # Lookups
    def role(self, name: str) -> str | None
    def personality(self, name: str) -> str | None
    def context(self, name: str) -> ContextFn | None
    def parser(self, name: str) -> ParserFn | None
    def client(self) -> LLMClient | None    # property

    # Observable callbacks
    def on_query(self, cb: Callable[[int, int, int], None]) -> None     # (eid, prompt_size, tick)
    def on_response(self, cb: Callable[[int, float, int, int], None]) -> None  # (eid, latency, response_size, tick)
    def on_error(self, cb: Callable[[int, str, str, int], None]) -> None       # (eid, error_type, msg, tick)

    # Prompt assembly
    def assemble_prompt(self, world: World, eid: int, agent: LLMAgent) -> tuple[str, str] | None
```

`assemble_prompt()` returns `(system_prompt, user_message)` or `None` if any referenced definition is missing. System prompt = role + "\n\n" + personality. User message = context_fn(world, eid).

> **Why two error classes:** Config errors (missing definitions) are programming mistakes -- they fire `on_error` for logging but don't penalize the entity because retrying won't help until you fix the config. Runtime errors (network failures, parse errors, timeouts) are transient -- they increment `consecutive_errors` and trigger cooldown to avoid hammering a failing backend.

> **Gotcha:** Config errors (missing role/personality/context) fire `on_error` but do NOT increment `consecutive_errors` or set `pending`. Runtime errors (query failure, parse failure, timeout) DO increment `consecutive_errors` and trigger cooldown at `max_retries`.

> **Gotcha:** Dispatch sorts eligible entities by `(-priority, eid)` for determinism. Higher priority entities query first. With equal priority, lower entity IDs go first. Combined with `max_queries_per_tick`, this means low-priority entities may be starved if high-priority ones always qualify.

### LLMSystem

```python
class LLMSystem:
    def __init__(self, manager: LLMManager) -> None
    def __call__(self, world: World, ctx: TickContext) -> None
    def shutdown(self) -> None
```

Three phases per tick:
1. **Harvest** -- check completed futures, parse responses, handle errors
2. **Timeout** -- cancel queries exceeding `config.query_timeout`
3. **Dispatch** -- submit new queries for eligible entities (sorted by `-priority, eid`)

Call `shutdown()` when the engine stops to clean up the thread pool.

> **Gotcha:** After `shutdown()`, the system becomes a no-op. Use `engine.on_stop()` to register `llm_system.shutdown` so it's called automatically when `run()` ends. If you're using `step()` externally, you must call `shutdown()` manually.

> **Gotcha:** ThreadPoolExecutor futures may not complete between rapid `engine.step()` calls in tests. If you're testing LLM responses, add a small `time.sleep(0.002)` in a harvest-wait loop, or use `MockClient(latency=0.0)` for instant responses.

### Parsers

```python
def strip_code_fences(text: str) -> str
def default_json_parser(response: str, blackboard: Blackboard) -> None
```
`default_json_parser`: strips code fences, `json.loads`, expects a dict, shallow-merges into `blackboard.data["strategy"]`.

### make_llm_system

```python
def make_llm_system(manager: LLMManager) -> LLMSystem
```
Factory function. Returns an `LLMSystem` instance that satisfies the `System` protocol.

---

## tick-colony -- Colony Simulation Primitives

`from tick_colony import ...`

High-level package for colony builder / roguelike simulations. Re-exports all extension packages plus colony-specific components, helpers, and LLM integration.

> **Why a mega-package:** Building a colony sim requires 10+ packages. tick-colony re-exports the most-used symbols from all extensions so you can `from tick_colony import Grid2D, Timer, FSM, ...` instead of importing from 10 separate modules. It also provides colony-specific components (NeedSet, StatBlock, Lifecycle) that don't belong in the general-purpose packages.

> **Tip:** If you're building a colony sim, start here. If you're building something that's NOT a colony sim (e.g., a puzzle game), import only the individual packages you need.

### At a Glance

| What | How |
|------|-----|
| Register all components | `register_colony_components(world)` |
| Full snapshot/restore | `cs = ColonySnapshot(grid, event_log, scheduler, cellmap, ability_mgr, registry)` |
| Add needs to entity | `world.attach(eid, NeedSet())` then `NeedHelper.add(ns, "hunger", 100, 100, 1.0, 20)` |
| Track entity age | `world.attach(eid, Lifecycle(born_tick=ctx.tick_number, max_age=500))` |
| Log events | `event_log.emit(tick, "raid", attackers=10)` |
| LLM context | `make_colony_context(grid, cellmap, event_log)` |
| Directive parsing | `make_directive_parser(handlers={"build": build_handler})` |
| Pressure monitoring | `engine.add_system(make_pressure_system(thresholds, event_log))` |

### Colony-Unique Exports

| Symbol | Kind | Description |
|--------|------|-------------|
| `NeedSet` | dataclass | Per-entity needs with decay and critical thresholds |
| `NeedHelper` | class | Static methods for need manipulation |
| `StatBlock` | dataclass | Named stats (`dict[str, float]`) |
| `Modifiers` | dataclass | Temporary stat modifiers with duration |
| `Container` | dataclass | Parent-child containment component |
| `ContainedBy` | dataclass | Marks an entity as contained |
| `Lifecycle` | dataclass | Birth tick and max age for mortality |
| `EventLog` | class | Ring-buffer event log with queries |
| `Event` | dataclass | Single event entry |
| `ColonySnapshot` | class | Extended snapshot/restore for colony state |
| `register_colony_components` | function | Register all colony component types |
| `make_need_decay_system` | function | System for need decay |
| `make_modifier_tick_system` | function | System for modifier expiration |
| `make_lifecycle_system` | function | System for age-based mortality |

### Colony LLM Integration

| Symbol | Kind | Description |
|--------|------|-------------|
| `make_resource_context` | function | Context builder for resource state |
| `make_population_context` | function | Context builder for population state |
| `make_spatial_context` | function | Context builder for spatial surroundings |
| `make_event_context` | function | Context builder for recent events |
| `make_colony_context` | function | Combined context builder |
| `DirectiveHandler` | type alias | `Callable[[dict[str, Any]], None]` |
| `make_directive_parser` | function | Parser factory for structured LLM directives |
| `PressureThresholds` | dataclass | Thresholds for pressure detection |
| `make_pressure_system` | function | System for monitoring colony pressure |

### Re-Exported Extensions

tick-colony re-exports these from extension packages so colony users need only one import:

From tick-spatial: `Grid2D`, `Pos2D`, `pathfind`, `make_spatial_cleanup_system`
From tick-schedule: `Timer`, `make_timer_system`
From tick-fsm: `FSM`, `FSMGuards`, `make_fsm_system`
From tick-blueprint: `BlueprintRegistry`
From tick-signal: `SignalBus`
From tick-event: `EventScheduler`, `EventGuards`, `EventDef`, `CycleDef`, `make_event_system`
From tick-command: `CommandQueue`, `make_command_system`, `expand_footprint`, `resolve_footprint`
From tick-atlas: `CellDef`, `CellMap`
From tick-ability: `AbilityDef`, `AbilityState`, `AbilityGuards`, `AbilityManager`, `make_ability_system`
From tick-resource: `Inventory`, `InventoryHelper`, `Recipe`, `ResourceDef`, `ResourceRegistry`, `can_craft`, `craft`, `make_resource_decay_system`
From tick-ai: `AIManager`, `BehaviorTree`, `Blackboard`, `UtilityAgent`, `Status`, `Node`, `make_bt_system`, `make_utility_system`
From tick-llm: `LLMAgent`, `LLMClient`, `LLMConfig`, `LLMManager`, `LLMSystem`, `MockClient`, `ContextFn`, `ParserFn`, `default_json_parser`, `strip_code_fences`, `make_llm_system`

### NeedSet & NeedHelper

```python
@dataclass
class NeedSet:
    data: dict[str, list[float]] = {}
```

Each value in `data` is a 4-element list with fixed indices:

| Index | Name | Meaning |
|-------|------|---------|
| `0` | current_value | Current need level (0.0 = depleted) |
| `1` | max_value | Upper bound for clamping |
| `2` | decay_rate | Amount subtracted per tick by `make_need_decay_system` |
| `3` | critical_threshold | Value at or below which `is_critical()` returns True |

Use `NeedHelper` to avoid indexing by hand.

**NeedHelper** (all methods are `@staticmethod`):

| Method | Signature | Description |
|--------|-----------|-------------|
| `add` | `(need_set: NeedSet, name: str, value: float, max_val: float, decay_rate: float, critical_threshold: float) -> None` | Add a new need |
| `get_value` | `(need_set: NeedSet, name: str) -> float` | Get current value (index 0) |
| `set_value` | `(need_set: NeedSet, name: str, value: float) -> None` | Set current value, clamped to [0, max] |
| `is_critical` | `(need_set: NeedSet, name: str) -> bool` | True if current <= threshold |
| `names` | `(need_set: NeedSet) -> list[str]` | All registered need names |

### StatBlock & Modifiers

```python
@dataclass
class StatBlock:
    data: dict[str, float] = {}     # stat_name -> base_value

@dataclass
class Modifiers:
    entries: list[list[Any]] = []   # Each: [stat_name, amount, duration]
                                    # duration: -1 = permanent, >0 = ticks remaining
```

```python
def effective(stat_block: StatBlock, modifiers: Modifiers, name: str) -> float
def add_modifier(modifiers: Modifiers, stat_name: str, amount: float, duration: int = -1) -> None
def remove_modifiers(modifiers: Modifiers, stat_name: str) -> None
```

### Container & ContainedBy

```python
@dataclass
class Container:
    items: list[int] = []       # Entity IDs of children
    capacity: int = -1          # -1 = unlimited

@dataclass
class ContainedBy:
    parent: int = 0             # Entity ID of parent
```

```python
def add_to_container(world, parent, child) -> bool    # Returns False if full
def remove_from_container(world, parent, child) -> None
def transfer(world, child, old_parent, new_parent) -> bool
def contents(world, parent) -> list[int]
def parent_of(world, child) -> int | None
```

### Lifecycle

```python
@dataclass
class Lifecycle:
    born_tick: int
    max_age: int      # -1 = immortal
```

### EventLog

```python
class EventLog:
    def __init__(self, max_entries: int = 0) -> None     # 0 = unlimited
    def emit(self, tick: int, type: str, **data: Any) -> None
    def query(self, type: str | None = None, after: int | None = None, before: int | None = None) -> list[Event]
    def last(self, type: str) -> Event | None
    def snapshot(self) -> list[dict[str, Any]]
    def restore(self, data: list[dict[str, Any]]) -> None
    def __len__(self) -> int
```

```python
@dataclass
class Event:
    tick: int
    type: str
    data: dict[str, Any]
```

### ColonySnapshot

Extended snapshot/restore that includes grid, event log, scheduler, cellmap, abilities, and resources.

```python
class ColonySnapshot:
    def __init__(
        self,
        grid: Grid2D | None = None,
        event_log: EventLog | None = None,
        scheduler: EventScheduler | None = None,
        cellmap: CellMap | None = None,
        ability_manager: AbilityManager | None = None,
        resource_registry: ResourceRegistry | None = None,
    ) -> None

    def snapshot(self, engine: Engine) -> dict[str, Any]
    def restore(self, engine: Engine, data: dict[str, Any]) -> None
```

`restore()` registers all colony components, calls `engine.restore()`, rebuilds the grid, and resets `agent.pending = False` on all `LLMAgent` entities (in-flight futures are lost on restore).

> **Why reset pending:** When you restore a snapshot, any in-flight LLM queries from the ThreadPoolExecutor are orphaned -- the futures still exist but the entity state they'll write to has been replaced. Resetting `pending = False` allows the LLM system to dispatch fresh queries for the restored state.

> **Tip:** Use `ColonySnapshot` instead of raw `engine.snapshot()`/`engine.restore()` for colony sims. It handles grid rebuilding, CellMap restoration, EventScheduler state, AbilityManager state, ResourceRegistry state, and LLMAgent reset in one call.

### register_colony_components

```python
def register_colony_components(world: World) -> None
```
Registers: `Pos2D`, `Timer`, `FSM`, `NeedSet`, `StatBlock`, `Modifiers`, `Container`, `ContainedBy`, `Lifecycle`, `Inventory`, `LLMAgent`, `Blackboard`.

### Colony System Factories

```python
def make_need_decay_system(
    on_critical: Callable[[World, TickContext, int, str], None] | None = None,
    on_zero: Callable[[World, TickContext, int, str], None] | None = None,
) -> Callable[[World, TickContext], None]

def make_modifier_tick_system() -> Callable[[World, TickContext], None]

def make_lifecycle_system(
    on_death: Callable[[World, TickContext, int, str], None] | None = None,
        # on_death(world, ctx, eid, cause) — cause is a string like "old_age"
) -> Callable[[World, TickContext], None]
```

### Context Builders

Factory functions returning `ContextFn = Callable[[World, int], str]` for LLM prompt assembly:

```python
def make_resource_context(resource_names: Sequence[str] | None = None, *, include_capacities: bool = False) -> ContextFn
def make_population_context(*, include_needs: bool = True, include_fsm_states: bool = True, include_lifecycle: bool = False) -> ContextFn
def make_spatial_context(grid: Grid2D, cellmap: CellMap | None = None, *, radius: int = -1) -> ContextFn
def make_event_context(event_log: EventLog, *, max_events: int = 20, event_types: Sequence[str] | None = None) -> ContextFn
def make_colony_context(
    grid: Grid2D | None = None,
    cellmap: CellMap | None = None,
    event_log: EventLog | None = None,
    *,
    resource_names: Sequence[str] | None = None,
    max_events: int = 10,
    spatial_radius: int = -1,
    include_strategy: bool = True,
) -> ContextFn
```

### Directive Parser

```python
DirectiveHandler = Callable[[dict[str, Any]], None]

def make_directive_parser(
    handlers: dict[str, DirectiveHandler],
    *,
    fallback: DirectiveHandler | None = None,
    write_strategy: bool = True,
) -> Callable[[str, Blackboard], None]
```

Expected LLM response format:
```json
{
    "directives": [
        {"type": "assign_task", "entity": 5, "task": "gather_wood"}
    ],
    "reasoning": "..."
}
```

Each directive's `"type"` is dispatched to the matching handler. Unknown types go to `fallback`.

### Pressure System

```python
@dataclass
class PressureThresholds:
    resource_change: float = 0.2
    population_change: float = 0.15
    critical_needs_ratio: float = 0.3
    event_types: Sequence[str] = ()
    event_burst: int = 5
    custom: dict[str, Callable[[World], float]] = {}

def make_pressure_system(
    thresholds: PressureThresholds | None = None,
    event_log: EventLog | None = None,
    *,
    check_interval: int = 5,
    min_priority: int = 0,
    on_pressure: Callable[[World, int, str, float], None] | None = None,
) -> Callable[[World, TickContext], None]
```

Monitors colony state and resets LLM agent cooldowns when pressure is detected. Check order: resource_change -> population_change -> critical_needs -> event_burst -> custom. First to fire wins.

> **Why pressure:** LLM agents have cooldowns to avoid excessive API calls. But when the colony is under stress (food running out, population crash, enemy attack), you want the AI to respond immediately rather than waiting out a 200-tick cooldown. The pressure system detects these situations and resets cooldowns so the LLM can react.

> **Gotcha:** Place the pressure system **before** the LLM system in your system registration order so cooldown resets take effect in the same tick's dispatch phase.

> **Gotcha:** Critical needs pressure has NO baseline requirement -- fires on first check if the ratio meets the threshold. Resource and population pressure need baseline initialization (first check always returns `False` because they compare against a baseline that hasn't been set yet). This means resource/population pressure won't fire until the second check interval.

> **Gotcha:** The `_check_events` function saves the *previous* `last_check_tick` before updating it. Without this, it would skip events that happened at the current tick.

---

## Cross-Cutting Patterns

### The System Pattern

Every extension follows the same pattern: components are dataclasses, behavior lives in system factory functions.

```python
# Pattern: make_*_system() returns a system function
system = make_timer_system(on_fire=my_callback)
engine.add_system(system)
```

Systems are `(World, TickContext) -> None`. They run in registration order. There is no dependency resolution -- order your `add_system()` calls carefully.

> **Why factory functions:** `make_timer_system(on_fire=...)` returns a closure that captures your callback. This avoids global state and lets you create multiple instances with different callbacks (e.g., one timer system for game timers, another for UI timers -- though in practice one is usually enough).

> **Why no dependency resolution:** Explicit ordering is simpler to reason about and debug. When something goes wrong, you can look at your `add_system()` calls and trace the exact execution order. Implicit dependency resolution introduces hidden coupling and makes order-dependent bugs harder to diagnose.

### The Registry Pattern

Several packages use named registries for definitions that are NOT serialized. This is the most important pattern to understand for snapshot/restore:

> **Why code-only registries:** Guard functions, AI actions, LLM parsers -- these are all Python callables. You can't serialize a function. So the pattern is: definitions live in code (registries), runtime state lives in data (components/snapshots). After restore, re-register definitions, then restore state.

| Registry | Defines | Must re-register after restore? |
|----------|---------|--------------------------------|
| `FSMGuards` | Guard predicates | Yes |
| `EventGuards` | Event guard predicates | Yes |
| `AbilityGuards` | Ability guard predicates | Yes |
| `AIManager` | Trees, actions, conditions, considerations | Yes |
| `LLMManager` | Roles, personalities, contexts, parsers | Yes |
| `BlueprintRegistry` | Entity templates | Yes |
| `ResourceRegistry` | Resource type definitions | Has own snapshot/restore |
| `EventScheduler` | Event definitions + runtime state | Re-register defs, then restore state |
| `AbilityManager` | Ability definitions + runtime state | Re-register defs, then restore state |

### Snapshot/Restore Checklist

This is the order that matters. Getting it wrong usually manifests as `SnapshotError` or silently broken state:

1. Call `world.register_component(ctype)` for every component type (or use `register_colony_components()`)
2. Re-register all definitions in FSMGuards, EventGuards, AbilityGuards, AIManager, LLMManager
3. Call `engine.restore(data)` (or `ColonySnapshot.restore()` which handles steps 1, 4, 5, and 6)
4. Rebuild spatial index: `grid.rebuild(world)`
5. Restore EventScheduler, AbilityManager, ResourceRegistry, CellMap state
6. Re-add all systems (systems are not serialized)
7. Reset `agent.pending = False` on all LLMAgent entities (ColonySnapshot does this automatically)

> **Tip:** Create a `setup_engine()` function that registers all components, definitions, and systems. Call it both at initial startup and after restore. This prevents the common bug of forgetting to re-register something after restore.

### Guard Pattern

Three packages use identically-structured guard registries:

```python
# FSMGuards: (World, EntityId) -> bool
# EventGuards: (World, EventScheduler) -> bool
# AbilityGuards: (World, AbilityManager) -> bool
```

All three have `.register(name, fn)`, `.check(name, ...)`, `.has(name)`, `.names()`.

> **Why string-named guards:** Transitions, events, and abilities reference guards by name string. This makes the data (FSM transitions, EventDef conditions) serializable. The guard *functions* live in the registry (code-only, not serialized). Missing guards raise `KeyError` at check time -- register them before the first tick.

### Detach-Before-Callback

Timer and Tween both detach the component **before** calling the completion callback. This enables safe chaining:

```python
def on_timer_fire(world, ctx, eid, timer):
    # Timer is already detached -- safe to attach a new one
    world.attach(eid, Timer(name="next", remaining=5))
```

> **Why this was necessary:** Early versions attached new timers that were immediately overwritten by the "cleanup" step. Detaching first solved this cleanly and established a pattern that Tween adopted. The cost is that the component in your callback is "dead" (already removed from the entity) -- but since it's passed as a parameter, you still have access to its fields.

### System Order Template

Here is a recommended system registration order for a full colony simulation using all packages:

```python
# 1. Input processing
engine.add_system(make_command_system(cmd_queue, on_accept, on_reject))

# 2. State machines
engine.add_system(make_fsm_system(guards, on_transition))

# 3. Timers and scheduling
engine.add_system(make_timer_system(on_fire))
engine.add_system(make_periodic_system(on_periodic))

# 4. Abilities
engine.add_system(make_ability_system(ability_mgr, ability_guards, on_start, on_end))

# 5. World events
engine.add_system(make_event_system(scheduler, event_guards, on_start, on_end))

# 6. Colony upkeep
engine.add_system(make_need_decay_system(on_critical, on_zero))
engine.add_system(make_modifier_tick_system())
engine.add_system(make_lifecycle_system(on_death))
engine.add_system(make_resource_decay_system(registry, on_spoiled))

# 7. Physics
engine.add_system(make_physics_system())
engine.add_system(make_collision_system(on_collision))

# 8. AI
engine.add_system(make_bt_system(ai_mgr, on_status))
engine.add_system(make_utility_system(ai_mgr, on_select))

# 9. LLM (pressure before LLM so cooldown resets take effect)
engine.add_system(make_pressure_system(thresholds, event_log))
engine.add_system(llm_system)

# 10. Cleanup and events (flush last)
engine.add_system(make_spatial_cleanup_system(grid))
engine.add_system(make_signal_system(bus))
```

This is a starting point -- adjust based on your game's specific needs.

---

*Generated for tick-engine v0.14.0. All 16 packages, all exported symbols.*
