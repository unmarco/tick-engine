# tick -- Technical Specification

**Version**: 0.1
**Date**: 2026-02-07
**Status**: Draft
**Author**: W72 Spec Writer

---

## 1. What This Is

`tick` is a minimal, general-purpose tick engine in Python. It is the skeleton of a game loop stripped of everything game-specific: no rendering, no physics, no input handling. What remains is the pure machinery of discrete simulation -- keeping time, maintaining state, and calling user-defined functions every tick.

The purpose is educational. The engine should make the tick pattern legible. Someone reading the code should come away understanding *exactly* how `Update()` works under the hood.

**One sentence**: A declarative engine that lets you describe state and behavior, then drives a fixed-timestep loop that evaluates and applies them tick by tick.

---

## 2. Core Concepts

### Tick

A tick is one discrete step of the simulation. The engine advances the world by exactly one tick at a time, at a fixed interval. Between ticks, nothing happens. During a tick, every registered system runs once, in order, against the current state.

A tick is NOT a frame. There is no visual output. The tick rate is a logical frequency (e.g., 20 ticks per second), not a render refresh rate.

### World

The world is the container for all simulation state. It holds entities and their associated data. There is exactly one world per engine instance. The world is the single source of truth -- systems read from it and write to it.

### Entity

An entity is an identity -- a unique handle that groups related pieces of state together. An entity has no behavior and no data of its own. It is a key into the world's state storage. Entities are created and destroyed through the world.

### Component

A component is a named, typed bundle of data attached to an entity. Components hold state, never logic. A "Position" component holds x and y values. A "Health" component holds current and max HP. An entity can have any combination of components. Components are plain Python dataclasses.

### System

A system is a function (or callable) that runs once per tick. Systems contain all the logic. A system receives the world (read/write access to all state) and the tick context (current tick number, delta time, elapsed time). Systems run in a deterministic, user-defined order.

Systems are the "verbs" of the simulation. They query the world for entities that have specific components, then read and mutate those components.

### Tick Context

A small, read-only object passed to every system on each tick, carrying temporal metadata:

- **tick_number**: Monotonically increasing integer. Starts at 0.
- **dt**: Fixed delta time in seconds between ticks (e.g., 0.05 for 20 TPS).
- **elapsed**: Total elapsed simulation time in seconds (tick_number * dt).

---

## 3. Architecture

The engine has four parts. Nothing else.

```
+---------------------------------------------------+
|                     Engine                         |
|                                                    |
|  +-----------+   +----------+   +--------------+   |
|  |   Clock   |   |  World   |   |  System      |   |
|  |           |   |          |   |  Pipeline    |   |
|  | fixed dt  |   | entities |   |              |   |
|  | tick count|   | components|  | [sys1, sys2] |   |
|  | elapsed   |   |          |   |              |   |
|  +-----------+   +----------+   +--------------+   |
|                                                    |
|  tick():                                           |
|    clock.advance()                                 |
|    ctx = clock.context()                           |
|    for system in pipeline:                         |
|        system(world, ctx)                          |
+---------------------------------------------------+
```

### Engine

The top-level coordinator. Owns the clock, the world, and the system pipeline. Exposes two primary operations: registering systems, and running the loop. The engine is the only thing the user instantiates directly.

### Clock

Tracks simulation time. Operates on a fixed timestep model. Each call to `advance()` increments the tick counter by one and updates elapsed time. The clock does NOT interact with wall-clock time -- it is purely a logical counter. Wall-clock pacing (sleeping to match real time) is the engine's responsibility, not the clock's.

### World

Stores all entities and their components. Provides operations to:

- Create an entity (returns a unique integer ID)
- Destroy an entity (removes it and all its components)
- Attach a component to an entity
- Detach a component from an entity
- Get a specific component from an entity
- Query for all entities that have a given set of component types

The world is a dumb container. It has no tick awareness and no lifecycle hooks. Systems are the only things that interpret or modify its contents.

### System Pipeline

An ordered list of systems. Each system is a callable with the signature `(world, ctx) -> None`. The pipeline runs them sequentially, in registration order, once per tick. There is no parallelism, no dependency graph, no priority system. Order is explicit and user-controlled.

---

## 4. API Surface

The user interacts with the engine through a small, flat API. The design priorities are: obvious, Pythonic, hard to misuse.

### Declaring Components

Components are plain Python dataclasses. No base class, no registration, no decorators. If it is a dataclass, it is a component.

Example concept: a "Position" component holds two floats (x, y). A "Velocity" component holds two floats (dx, dy). A "Lifetime" component holds a single float (remaining seconds). These are just data containers -- the user defines them as standard Python dataclasses.

### Declaring Systems

A system is any callable that accepts `(world, ctx)`. It can be a plain function or an instance with `__call__`. No base class required. The user writes a function, registers it, and the engine calls it every tick.

### Engine Setup and Execution

The user creates an engine with a target ticks-per-second. They register systems in the order they should run. They seed the world with initial entities and components. Then they call `run()`.

The engine should support three modes of execution:

1. **run(n)** -- Run exactly n ticks, then stop. Deterministic. Ideal for testing and scripted scenarios.
2. **run_forever()** -- Run indefinitely until explicitly stopped. The engine paces itself to wall-clock time, sleeping between ticks to maintain the target tick rate. Stopped via a flag or signal.
3. **step()** -- Run exactly one tick. Gives the caller full manual control over the loop. Useful for debugging, integration into external loops, or educational step-through.

### World Manipulation

Systems interact with the world through direct method calls. The world should feel like a simple data store:

- Creating an entity returns an integer ID.
- Attaching a component to an entity is a single call passing the entity ID and a component instance.
- Querying is by component type: "give me all entities that have both Position and Velocity" returns an iterable of (entity_id, component_tuple) pairs.
- Getting a single component from a known entity is a direct lookup.

### Lifecycle Hooks (Minimal)

Two optional hooks, both registered the same way as systems:

- **on_start**: Called once before the first tick. Use for initialization that depends on the fully-assembled world.
- **on_stop**: Called once after the last tick. Use for cleanup or final state reporting.

These are NOT per-entity or per-component lifecycle events. There are no component-added or entity-destroyed callbacks. Keep it simple.

---

## 5. Tick Lifecycle

One tick proceeds as follows, every time, without exception:

```
1. Clock advances
   - tick_number += 1
   - elapsed = tick_number * dt
   - A TickContext is created with (tick_number, dt, elapsed)

2. Systems execute in pipeline order
   - For each system in the pipeline:
       - system(world, ctx)
   - Systems may create/destroy entities, add/remove components,
     and mutate component data freely.
   - Changes are immediately visible to subsequent systems
     in the same tick.

3. Tick completes
   - Control returns to the engine loop.
   - If pacing to wall-clock time, the engine sleeps for
     any remaining time in the tick budget.
```

There is no batching of entity creation/destruction. No deferred operations. No event queue. Changes are immediate and sequential. This is simpler to reason about and sufficient for a learning engine.

**Important**: the first tick is tick_number=1, not 0. Tick 0 does not exist. The on_start hook runs before tick 1.

---

## 6. Time Model

**Fixed timestep, mandatory.**

The engine runs at a user-specified ticks-per-second (TPS). The delta time `dt` is `1.0 / TPS` and never changes during execution. Every tick sees the same dt. This makes the simulation deterministic -- given the same initial state and systems, the same sequence of ticks always produces the same results.

### Wall-Clock Pacing

When running in `run_forever()` mode, the engine uses wall-clock time to pace itself:

```
target_tick_duration = 1.0 / TPS

loop:
    start = wall_clock_now()
    execute_one_tick()
    elapsed_real = wall_clock_now() - start
    sleep(max(0, target_tick_duration - elapsed_real))
```

If a tick takes longer than the budget, the engine does NOT try to catch up with multiple ticks. It simply proceeds to the next tick. This avoids the "spiral of death" where falling behind causes more work, which causes falling further behind. For a learning engine, simplicity beats fidelity.

### No Interpolation

There is no interpolation, extrapolation, or render-phase alpha blending. Those concepts exist to smooth visual output between ticks. This engine has no visual output. The tick is the only unit of time that matters.

---

## 7. Data Model

### Entity Storage

Entities are integers. The world maintains a monotonically increasing counter for ID generation. Destroyed entity IDs are never reused (within a single engine run). This avoids aliasing bugs where a new entity accidentally inherits references meant for a dead one.

### Component Storage

Components are stored in a dictionary-of-dictionaries structure, conceptually:

```
components[ComponentType][entity_id] -> component_instance
```

This layout optimizes for the primary access pattern: "give me all entities that have ComponentType X." Iterating over all instances of a component type is a single dictionary iteration. This is the operation systems perform most frequently.

The secondary access pattern -- "give me component X for entity E" -- is a two-step dictionary lookup, which is also fast.

### Querying

The world supports querying for entities that possess ALL of a given set of component types. This is the fundamental operation that systems use.

The query returns pairs of (entity_id, tuple_of_components) for every entity that has every requested component type. The components in the tuple are in the same order as the types in the query. This lets systems destructure results cleanly.

Single-component queries are a degenerate case and should be equally convenient.

### No Change Tracking

The world does not track what changed between ticks. There is no dirty flag, no diff, no event emission on component mutation. Systems that need to detect change must implement it themselves (e.g., by storing a "previous_value" component). This is a conscious simplicity trade-off.

---

## 8. Demo Scenario

To validate the engine, a simple demo that exercises all the core concepts without being a game.

**Scenario: Population Dynamics**

A small simulation of abstract "organisms" that age, reproduce, and die.

- **Entities**: Each organism is an entity.
- **Components**:
  - Age (current age in ticks, max lifespan)
  - Energy (current energy level)
  - Reproducible (a marker indicating the entity can reproduce, with a cooldown counter)
- **Systems** (run in this order each tick):
  1. **Aging System**: Increments age for all entities with Age. If age exceeds max lifespan, destroy the entity.
  2. **Energy System**: Decreases energy each tick. If energy hits zero, destroy the entity.
  3. **Reproduction System**: For entities with Reproducible and Energy above a threshold, create a new entity (child) with initial Age and Energy. Deduct energy cost from parent. Reset cooldown.
  4. **Census System**: Every N ticks, print the total population count, average age, and average energy. Pure read-only observation.

This demo proves:
- Entity creation and destruction mid-simulation
- Multiple component types on a single entity
- Systems querying by component type
- Systems mutating state that later systems see in the same tick
- Deterministic behavior over a fixed number of ticks

The demo runs for a fixed number of ticks (e.g., 500) and prints periodic census reports. No visualization. The output is text.

---

## 9. Project Structure

```
tick/
    __init__.py          -- Public API re-exports
    engine.py            -- Engine (loop, pacing, lifecycle)
    clock.py             -- Clock and TickContext
    world.py             -- World (entity/component storage, queries)
    types.py             -- Shared type aliases and protocols
examples/
    population.py        -- The demo scenario above
tests/
    test_engine.py       -- Engine lifecycle, tick counting, pacing
    test_world.py        -- Entity CRUD, component attach/detach, queries
    test_clock.py        -- Clock advancement, context generation
    test_integration.py  -- Multi-system scenarios, determinism checks
pyproject.toml           -- Project metadata, Python 3.11+ requirement
```

Six source files (four engine + one types + one init), one example, four test files. That is the entire project.

---

## 10. What Is Explicitly Out of Scope

These are all things a real engine might want. This engine does not want them. They are forbidden from v0.1.

| Concern | Why it is out |
|---|---|
| Rendering / display | No visual output of any kind. Print statements in systems are fine. |
| Input handling | The engine has no concept of user input. Systems can hard-code behavior. |
| Networking | Single-process, single-thread only. |
| Physics | No collision, no forces, no spatial partitioning. |
| ECS optimization | No archetypes, no sparse sets, no component pools. Dictionaries are fine. |
| Parallelism | Systems run sequentially. No threads, no async. |
| Serialization | No save/load. State lives and dies with the process. |
| Events / messaging | No event bus, no pub/sub between systems. Direct state mutation only. |
| Component lifecycle hooks | No on-attach, on-detach, on-destroy callbacks. |
| Entity hierarchy | No parent-child relationships. Entities are flat. |
| Hot reloading | No live code swapping. |
| Plugin system | No dynamic loading of systems or components. |
| Configuration files | All setup is done in Python code. |

---

## 11. Design Decisions and Rationale

### Why fixed timestep only?

Variable timestep introduces floating-point non-determinism. Two runs of the same simulation can produce different results depending on how fast the machine executes each tick. For a learning engine, determinism is essential -- it lets the user reason about state transitions with certainty. Fixed timestep is also simpler to implement and explain.

Reference: Glenn Fiedler's "Fix Your Timestep" is the canonical argument. See also Robert Nystrom's [Game Loop pattern](https://gameprogrammingpatterns.com/game-loop.html).

### Why no deferred entity destruction?

Many ECS engines defer entity destruction to the end of the tick to avoid iterator invalidation. This engine uses dictionary-based storage where deletion during iteration is safe if done carefully, and more importantly, deferred destruction is harder to reason about. If a system destroys an entity, later systems in that tick should not see it. Immediate destruction matches the user's mental model.

**Implementation note for the code-writer**: Systems should collect entity IDs to destroy and then destroy them after iteration, not during. The world API should support this pattern naturally. The "no deferral" principle means destruction takes effect within the same tick -- but within a single system's execution, the system should finish its query loop before destroying.

### Why dictionaries instead of arrays?

Array-based component storage (like archetype ECS) is faster for iteration but far more complex to implement and explain. Dictionary-based storage is idiomatic Python, easy to understand, and fast enough for any workload this engine will ever see. This is a teaching tool, not a performance tool.

### Why no events?

Events add a second communication channel between systems (the first being shared state). Two channels means two things to learn, two things that can go wrong, and two mental models to maintain. Shared mutable state is sufficient for a minimal engine and is easier to trace/debug.

### Why no base classes?

Components are dataclasses. Systems are callables. No base class for either. This keeps the API surface tiny, avoids inheritance complexity, and makes the engine feel like Python rather than like a framework. The user never has to wonder "what methods do I inherit?" because the answer is: none.

---

## 12. Success Criteria

The engine is complete when:

1. A user can define components as plain dataclasses and systems as plain functions.
2. The engine runs a fixed-timestep loop that calls systems in order.
3. Systems can create/destroy entities and add/remove/mutate components.
4. The population demo runs for 500 ticks and produces deterministic output.
5. Running the same demo twice produces identical results.
6. The entire codebase (excluding tests) is under 500 lines.
7. There are zero external dependencies.
8. A competent Python developer can read and understand the entire engine in under 30 minutes.

---

## 13. Open Questions

1. **Should the world support single-entity component access without a query?** Something like `world.get(entity_id, Position)` as a direct lookup, separate from the multi-entity query API. Leaning yes for ergonomics.

2. **Should systems be able to signal "stop the engine"?** For example, a system detects a termination condition and wants to end the loop. Options: (a) systems set a flag on the engine/world, (b) systems raise a special exception, (c) only the caller controls stopping. Leaning toward (a) -- a simple `world.stop()` or `ctx.stop()` method.

3. **Tick 0 or Tick 1?** This spec says the first tick is tick_number=1. An argument can be made for tick_number=0 (zero-indexed, Pythonic). The code-writer should pick one and be consistent.

4. **Should the world have a name or metadata?** Useful for logging/debugging but not essential. Defer to code-writer's judgment.

---

## References

- Robert Nystrom, [Game Loop - Game Programming Patterns](https://gameprogrammingpatterns.com/game-loop.html)
- Glenn Fiedler, "Fix Your Timestep!" (classic game loop article)
- Andre Leite, [Taming Time in Game Engines](https://andreleite.com/posts/2025/game-loop/fixed-timestep-game-loop/) (2025)
- [Entity Component System - Wikipedia](https://en.wikipedia.org/wiki/Entity_component_system)
- [esper](https://github.com/benmoran56/esper) -- a minimal Python ECS, useful as a reference for API feel
- [ECS FAQ](https://github.com/SanderMertens/ecs-faq) -- comprehensive overview of ECS patterns and trade-offs
