# tick -- Technical Specification (v0.2 Series)

**Version**: 0.2 series (covers v0.1.1 through v0.3.0)
**Date**: 2026-02-07
**Status**: Draft
**Author**: W72 Spec Writer
**Prerequisite**: SPEC.md (v0.1, shipped)

---

## 0. How to Read This Document

This specification covers multiple releases. Each is self-contained and can be implemented independently, but they build on each other.

| Release | Codename | Theme |
|---------|----------|-------|
| v0.1.1 | "Guard Rails" | Robustness patch -- alive-entity guards |
| v0.2.0 | "Replay" | Seed-able RNG + serialization |
| v0.3.0 | "Control" | System controls + (optionally) event bus |

The ordering reflects dependency analysis. Serialization needs deterministic RNG to be meaningful (you cannot replay a simulation that used `random.random()`). System controls and events are independent of the first two features and more architecturally invasive, so they come last.

---

## Part 1: v0.1.1 -- Alive-Entity Guards

### 1.1. Problem Statement

The v0.1 World API has inconsistent behavior when operating on dead (despawned) or never-created entity IDs:

| Method | Current behavior with dead entity | Problem |
|--------|----------------------------------|---------|
| `attach()` | Silently succeeds, stores orphaned component data | Ghost data accumulates; queries skip it (alive check), but component store grows forever |
| `get()` | Raises `KeyError("has no component")` | Correct outcome, wrong reason -- it works by accident because `despawn()` cleans up components. If component cleanup had a bug, `get()` would return stale data. |
| `has()` | Returns `False` | Same accidental correctness. Checks component store, which happens to be empty after despawn. No explicit alive check. |

All three methods should fail fast and explicitly when given a dead entity ID. Silent corruption is worse than a loud error.

### 1.2. Specified Changes

**`attach(entity_id, component)`**: Raise a dedicated error if `entity_id` is not in the alive set. The error message should name the entity ID and the component type being attached.

**`get(entity_id, component_type)`**: Raise a dedicated error if `entity_id` is not in the alive set. This replaces the indirect `KeyError` that currently occurs only as a side effect of component cleanup. The error should be raised BEFORE checking the component store.

**`has(entity_id, component_type)`**: Return `False` if `entity_id` is not in the alive set. Do NOT raise -- `has()` is a predicate, and predicates should not throw. The alive check should come first, short-circuiting the component store lookup.

**`detach(entity_id, component_type)`**: No change. Detaching from a dead entity is already a no-op (the component was removed by `despawn()`). Making this stricter adds no safety and would break cleanup patterns where systems call `detach()` defensively.

**`despawn(entity_id)`**: No change. Double-despawn is already a safe no-op via `discard()`.

### 1.3. Error Type

Use a new `DeadEntityError` that extends `KeyError`. This preserves backward compatibility for code that catches `KeyError` from `get()`, while giving callers the option to catch the more specific type.

The error should carry the entity ID as a machine-readable attribute, not just in the message string.

### 1.4. Migration Impact

This is a **breaking behavioral change** for `attach()`. Code that attaches components to dead entities will now raise where it previously succeeded silently. In practice, this only affects buggy code -- no correct program should attach to a dead entity.

**Who is affected**:
- Any system that calls `attach()` without first checking `world.alive()`.
- Code that attaches components to entity IDs obtained from a previous tick where the entity may have been despawned.

**Migration path**: Add an `if world.alive(eid):` guard before `attach()` calls in systems that operate on entity IDs from external sources (not from queries, which already filter dead entities).

**Existing tests**: The test `test_get_despawned_entity_raises_key_error` will continue to pass because `DeadEntityError` extends `KeyError`. No other existing tests attach to dead entities.

### 1.5. Test Requirements

New tests required:

- `attach()` to a despawned entity raises `DeadEntityError`
- `attach()` to a never-created entity ID raises `DeadEntityError`
- `get()` on a despawned entity raises `DeadEntityError` (not generic `KeyError`)
- `has()` on a despawned entity returns `False` (already passes, but add explicit test)
- `has()` on a never-created entity ID returns `False`
- `DeadEntityError` is a subclass of `KeyError`
- `DeadEntityError` carries the entity ID as an attribute

### 1.6. Success Criteria

- All existing tests continue to pass without modification.
- The six new tests above pass.
- `DeadEntityError` is exported from the `tick` package public API.
- The population demo continues to produce identical deterministic output.

---

## Part 2: v0.2.0+ Features

### 2. Dependency Analysis and Phasing

The four requested features have the following dependency relationships:

```
Seed-able RNG -----> Serialization
     |                    |
     |  (RNG state must   |  (snapshot must capture RNG
     |   be deterministic  |   state to enable replay)
     |   to matter)        |
     v                    v
  [v0.2.0]           [v0.2.0]

System Controls -----> Event Bus
     |                    |
     |  (phases provide   |  (events are optional;
     |   natural hook     |   if added, they interact
     |   points for       |   with system ordering)
     |   events)          |
     v                    v
  [v0.3.0]           [v0.3.0, opt-in]
```

**Why this grouping**:

- **v0.2.0 (RNG + Serialization)**: Serialization without seed-able RNG is incomplete -- you cannot replay a simulation that used Python's global `random` module because the RNG state is not captured. These two features are a natural pair: seed-able RNG makes simulations reproducible, serialization makes them restorable. Together they unlock replay and time-travel debugging.

- **v0.3.0 (System Controls + Event Bus)**: System controls (enable/disable, phases, variable tick rate) change the engine's execution model. The event bus, if approved, is a new communication channel that interacts with system ordering. Both features touch the engine's core loop and system pipeline. Implementing them together allows a cohesive redesign of the system pipeline rather than two separate refactors.

---

## 3. v0.2.0 -- Seed-able RNG

### 3.1. Problem Statement

The v0.1 engine guarantees determinism: same initial state + same systems = same results. But this guarantee breaks the moment a system calls `random.random()` or any other source of randomness. The population demo is deterministic only because it uses no randomness -- a severe limitation for interesting simulations.

The engine should provide a built-in, seed-controlled random number generator that systems can use without breaking determinism. Two runs with the same seed must produce identical results, tick by tick.

### 3.2. Design

**Seed configuration**: The Engine constructor accepts an optional `seed` parameter (integer). If omitted, a seed is auto-generated (from `os.urandom` or similar) and recorded so it can be retrieved later for reproduction.

**RNG access**: Systems access the RNG through the `TickContext`, via a property named `random`. This returns a standard-library `random.Random` instance, seeded and owned by the engine.

Conceptual usage from a system's perspective:

    The system receives `ctx` as usual. It calls `ctx.random` to get a
    Random instance. It uses methods like `.random()`, `.randint()`,
    `.choice()`, `.gauss()`, etc. -- the full `random.Random` API.

**Why `ctx.random` and not `world.random`**: The RNG is temporal, not spatial. It belongs to the simulation's timeline, not to the entity store. Putting it on the context makes this conceptual boundary clear and keeps the World as a dumb data container (per v0.1 design).

**Why not a separate `rng` parameter to systems**: Adding a third parameter to every system function would break the v0.1 API. The context already exists as the "bag of per-tick metadata." Extending it is the least invasive option.

### 3.3. Determinism Guarantee

The RNG state must be advanced in a deterministic order. Since systems run sequentially in pipeline order, and each system's calls to `ctx.random` happen in a deterministic sequence (given deterministic inputs), the overall RNG sequence is deterministic.

**Critical rule**: There must be exactly ONE `Random` instance per engine. Systems must NOT create their own `Random` instances (this is a documentation/convention concern, not something the engine can enforce). The engine's RNG is the single source of randomness.

**Seed retrieval**: The engine should expose the active seed via a read-only property, so that users can record it for later reproduction. Conceptually: `engine.seed` returns the integer seed in use.

### 3.4. Interaction with Serialization

The RNG's internal state must be serializable (covered in Section 4). When restoring a snapshot, the RNG state is restored along with the world state, so that subsequent ticks produce the same random sequence as the original run. Python's `random.Random` supports `getstate()` and `setstate()` for this purpose.

### 3.5. TickContext Extension

The `TickContext` NamedTuple gains one new field:

| Field | Type | Description |
|-------|------|-------------|
| `random` | `random.Random` | The engine's seeded RNG instance |

This is an **additive, backward-compatible change**. Existing code that unpacks `TickContext` positionally will break only if it unpacks all fields -- but TickContext is a NamedTuple accessed by name, and the `request_stop` callable is always accessed as `ctx.request_stop()`, not by position. Adding a field at the end is safe for named access.

**Consideration**: If positional unpacking is a concern, the implementation team may choose to place `random` before `request_stop` (making `request_stop` always last as the least-used field) or to migrate TickContext from NamedTuple to a frozen dataclass. The spec does not mandate a specific TickContext implementation strategy -- only the public API surface.

### 3.6. Out of Scope

- Per-system RNG isolation (each system getting its own independent stream). This would enable system-level replay but adds substantial complexity. Defer to v0.4+.
- Cryptographic randomness. This is a simulation engine, not a security tool.
- Deterministic floating-point across platforms. Python floats are IEEE 754, but cross-platform bit-exact reproducibility is not guaranteed and not a goal.

### 3.7. Test Requirements

- Two runs with the same seed produce identical random sequences across 100 ticks.
- Two runs with different seeds produce different random sequences.
- The seed is retrievable from the engine after construction.
- Auto-generated seeds (no seed argument) produce valid, usable RNG.
- The RNG state is independent of wall-clock time (no time-based seeding in the hot path).
- Systems that use `ctx.random` maintain full simulation determinism.

### 3.8. Success Criteria

- The population demo can be extended with random variation (random lifespans, random energy costs) and still produce deterministic output given the same seed.
- A new example or test demonstrates: run simulation 50 ticks, record seed and final state, run again from scratch with same seed, assert identical final state.

---

## 4. v0.2.0 -- Serialization

### 4.1. Problem Statement

The v0.1 engine's state lives and dies with the process. There is no way to:

- Save a simulation at tick N and resume later.
- Rewind to a previous tick for debugging.
- Compare two simulation runs at the same tick.
- Checkpoint long-running simulations for crash recovery.

Serialization unlocks all of these. It is the foundation for replay, time-travel debugging, and operational resilience.

### 4.2. Design Philosophy

**Snapshot, not streaming.** The serialization model is point-in-time snapshots, not a continuous event log. A snapshot captures everything needed to resume the simulation from that exact tick. This is simpler to implement and reason about than event sourcing.

**Generic, not per-component.** The serialization system should handle any dataclass component without requiring per-component serialization logic. Users should not need to write custom serializers for their components. The engine relies on dataclasses being introspectable via `dataclasses.fields()` and `dataclasses.asdict()`.

**Systems are NOT serialized.** Systems are functions. Functions are not data. A snapshot captures the world state and temporal state (tick number, RNG state), but the system pipeline is assumed to be reconstructed by the application on restore. This is the same pattern as database migrations: the schema (systems) is in code, the data (world state) is in the snapshot.

### 4.3. What a Snapshot Contains

A snapshot captures the complete simulation state at a specific tick:

| Component | Contents |
|-----------|----------|
| **Tick number** | The current tick number at time of snapshot |
| **TPS** | The ticks-per-second setting |
| **RNG state** | The full internal state of the `random.Random` instance (via `getstate()`) |
| **Entity registry** | The set of alive entity IDs and the next-ID counter |
| **Component data** | For every alive entity, every attached component: its type (as a qualified name string) and its field values |

### 4.4. Serialization Format

The snapshot should serialize to a Python dictionary structure that is JSON-compatible. This means:

- Component field values must be reducible to JSON primitives (strings, numbers, booleans, None, lists, dicts).
- Component types are identified by their fully qualified name (module + class name).
- The RNG state tuple is stored as-is (it contains only JSON-compatible primitives).

**Why JSON-compatible dict and not pickle**: Pickle is Python-specific, version-fragile, and a security risk for untrusted data. A JSON-compatible dict can be serialized to JSON, YAML, MessagePack, or any other format the user prefers. The engine provides the dict; the user chooses the wire format.

**Why not mandate JSON file I/O**: File I/O is not the engine's concern. The engine converts state to/from a dictionary. Writing that dictionary to disk, a database, or a network socket is the application's responsibility. The engine should not import `json` or touch the filesystem.

### 4.5. API Surface

The serialization API lives on the World (for state) and Engine (for full snapshot including temporal data):

**Engine-level** (full simulation snapshot):

- `engine.snapshot()` -- Returns a dictionary representing the complete simulation state at the current tick. Includes tick number, TPS, RNG state, and all world data.
- `engine.restore(snapshot_dict)` -- Accepts a snapshot dictionary and restores the engine to that state. Resets tick number, RNG state, and replaces all world contents. Systems are NOT affected (they remain as currently registered).

**World-level** (entity/component data only):

- `world.snapshot()` -- Returns a dictionary of entity and component data only. No temporal metadata.
- `world.restore(snapshot_dict)` -- Replaces all world contents with the snapshot data. Clears existing entities and components first.

The two-level API lets users choose granularity. `engine.snapshot()` is for full replay. `world.snapshot()` is for comparing or transferring entity state between worlds.

### 4.6. Component Type Resolution

The tricky part of deserialization is reconstructing component instances from their serialized form. The snapshot stores component types as fully qualified names (e.g., `"examples.population.Age"`). On restore, the engine must resolve these names back to actual Python classes.

**Strategy: Component Registry.** The engine maintains a registry mapping qualified names to component classes. Components are registered explicitly by the user before restoring a snapshot. This avoids the security risks of dynamic `importlib` resolution and makes the dependency explicit.

Conceptually:

    Before calling `engine.restore()`, the user registers all component
    types that might appear in the snapshot. The engine uses this registry
    to reconstruct component instances during restore.

**Auto-registration**: As a convenience, the engine should auto-register any component type it encounters during `attach()`. This means that in the common case (save and load within the same process), no explicit registration is needed. Explicit registration is only required when loading a snapshot from a different process or a previous session.

### 4.7. Handling Complex Component Fields

The spec mandates that components are "plain dataclasses." For serialization purposes, this means component fields should contain:

- Primitives: int, float, str, bool, None
- Collections of primitives: list, dict, tuple, set
- Nested dataclasses (recursive serialization)

**Not supported** (and documented as such):
- Fields containing functions, lambdas, or callables
- Fields containing non-dataclass class instances
- Fields containing circular references
- Fields containing file handles, sockets, or OS resources

If a component contains unsupported field types, `snapshot()` should raise a clear error at serialization time, not silently produce corrupt data.

### 4.8. Snapshot Versioning

Every snapshot dictionary should include a `version` key indicating the snapshot format version. This enables future changes to the snapshot format without breaking old snapshots.

Initial version: `1`.

The `restore()` method checks the version and raises a clear error if it encounters an unsupported version, rather than silently misinterpreting data.

### 4.9. Interaction with Alive-Entity Guards (v0.1.1)

During `restore()`, the world is cleared and rebuilt. The alive-entity guards from v0.1.1 apply normally -- restored entities are added to the alive set, and subsequent operations respect the guards.

### 4.10. Out of Scope

- **Delta snapshots** (storing only changes since last snapshot). Full snapshots are simpler and sufficient for the scale this engine targets.
- **Snapshot compression**. The user can compress the JSON output if needed.
- **Automatic checkpointing** (snapshot every N ticks). Trivial to implement as a system; no engine support needed.
- **System serialization**. Functions are not data. The user reconstructs the system pipeline.
- **Cross-language compatibility**. Snapshots are Python-dict-shaped, not a language-neutral format.

### 4.11. Test Requirements

- Snapshot and restore produces identical world state (entity IDs, component values).
- Snapshot and restore preserves tick number and RNG state.
- Simulation resumed from a snapshot produces identical results to an uninterrupted run.
- Snapshot of an empty world succeeds and restores correctly.
- Snapshot with multiple component types on a single entity round-trips correctly.
- Restore clears pre-existing world state before loading.
- Restore with an unregistered component type raises a clear error.
- Snapshot with unsupported field types (e.g., a lambda in a component) raises at serialization time.
- Snapshot version mismatch raises a clear error on restore.

### 4.12. Demo Enhancement

Extend the population demo (or create a new example) to demonstrate:

1. Run 250 ticks, take a snapshot.
2. Continue to tick 500, record final state.
3. Restore the snapshot (back to tick 250).
4. Continue to tick 500 again, record final state.
5. Assert the two final states are identical.

This proves that serialization + seed-able RNG together enable perfect replay.

### 4.13. Success Criteria

- `engine.snapshot()` returns a JSON-serializable dictionary for any world state composed of dataclass components with primitive fields.
- `engine.restore(snapshot)` restores the simulation to the exact state at snapshot time.
- A simulation paused at tick N, saved, restored, and resumed produces identical output to an uninterrupted run through the same tick range.
- The snapshot dictionary is human-readable when pretty-printed as JSON.
- No external dependencies are required for serialization.

---

## 5. v0.3.0 -- System Controls

### 5.1. Problem Statement

The v0.1 system pipeline is a flat list. Every system runs every tick, in the same order, at the same rate. This is beautifully simple but limiting:

- **No way to disable a system temporarily.** A debug-logging system that should only run during development must be removed entirely or must check an internal flag every tick.
- **No way to group systems into phases.** An "input processing" system and a "physics" system and a "rendering" system are conceptually different phases, but the engine treats them identically.
- **No way to change tick rate.** Fast-forward (10x speed) or slow-motion (0.1x speed) requires stopping and recreating the engine.

### 5.2. Feature A: System Enable/Disable

**Design**: Each system in the pipeline has an enabled/disabled state. Disabled systems are skipped during tick execution but remain in the pipeline at their registered position. Re-enabling a system restores it to its original position without re-registration.

**API Surface**:

Systems need to be identifiable. In v0.1, systems are anonymous callables -- there is no way to refer to "the aging system" after registration. Two approaches:

**Option chosen: Name-based identification.** `add_system()` accepts an optional `name` parameter. If omitted, the name is derived from the callable (function name, or class name for callable objects). Names must be unique within the pipeline.

- `engine.add_system(system, name=None)` -- Register with optional explicit name.
- `engine.enable_system(name)` -- Enable a previously disabled system. No-op if already enabled.
- `engine.disable_system(name)` -- Disable a system. No-op if already disabled.
- `engine.system_enabled(name)` -- Returns boolean indicating current state.

**Why not remove/re-add**: Removing and re-adding changes the system's position in the pipeline. Enable/disable preserves ordering, which is critical for determinism.

**Why names and not references**: Holding references to function objects is fragile (lambdas, closures, decorated functions may produce different object identities). String names are stable, inspectable, and debuggable.

### 5.3. Feature B: System Phases

**Design**: The system pipeline is divided into named phases. Each phase is a group of systems that run together, in order. Phases themselves run in a fixed order. This replaces the flat list with a two-level structure: phases contain systems.

**Default phases** (if user does not configure custom phases):

| Phase | Purpose | Runs |
|-------|---------|------|
| `pre_tick` | Setup, input processing, preparation | Before main logic |
| `tick` | Core simulation logic | Main phase |
| `post_tick` | Cleanup, observation, bookkeeping | After main logic |

**API Surface**:

- `engine.add_system(system, phase="tick", name=None)` -- The `phase` parameter defaults to `"tick"` for backward compatibility. Systems registered without specifying a phase go into the `tick` phase, preserving v0.1 behavior.

**Custom phases**: For advanced users, the Engine constructor accepts a `phases` parameter -- an ordered sequence of phase names. If provided, it replaces the default three phases. This enables domain-specific phase structures (e.g., a physics engine might want `"broad_phase"`, `"narrow_phase"`, `"resolve"`, `"integrate"`).

**Phase execution order** is the order in which phases are defined (constructor argument order or default order). Within a phase, systems run in registration order.

### 5.4. Feature C: Variable Tick Rate

**Design**: The engine's TPS (ticks per second) can be changed at runtime. This affects wall-clock pacing in `run_forever()` mode. It does NOT affect `dt` within the simulation -- the simulation timestep remains fixed for determinism.

Wait -- this needs careful thought. There are two different things a user might mean by "variable tick rate":

**Option 1: Variable pacing, fixed dt.** The wall-clock sleep between ticks changes, but `dt` stays the same. At 2x speed, ticks happen twice as fast in real time, but each tick still advances simulation time by the same `dt`. The simulation runs identically; it just runs faster or slower relative to the wall clock. This is "fast-forward" in the cinematic sense.

**Option 2: Variable dt.** The actual simulation timestep changes. This breaks the fixed-timestep guarantee and determinism. This is NOT what we want.

**Decision: Option 1.** Variable pacing, fixed dt. The engine gains a `speed` multiplier that affects only the wall-clock sleep calculation.

- `engine.speed` -- Read/write property. Default `1.0`. A value of `2.0` means ticks happen at 2x real-time speed. A value of `0.5` means half speed. A value of `0.0` means "run as fast as possible" (no sleep). Negative values are invalid.

**Interaction with `run(n)`**: The `speed` multiplier has NO effect on `run(n)` or `step()`. These modes do not pace to wall-clock time. `speed` only affects `run_forever()`.

**Interaction with serialization**: The `speed` multiplier is NOT included in snapshots. It is a playback concern, not a simulation-state concern. Restoring a snapshot does not change the current speed.

### 5.5. Backward Compatibility

All three features are backward-compatible:

- `add_system(system)` with no extra arguments behaves identically to v0.1.
- Systems are enabled by default.
- The default phase configuration produces a single `"tick"` phase containing all systems, matching v0.1's flat pipeline.
- `speed` defaults to `1.0`, matching v0.1 pacing behavior.

### 5.6. Out of Scope

- **System dependencies / DAG scheduling.** Systems run in registration order within their phase. No automatic dependency resolution.
- **Per-system tick rates** (e.g., "run this system every 5th tick"). This can be implemented in userland with `if ctx.tick_number % 5 == 0: return`.
- **System priority numbers.** Phases + registration order is sufficient. Numeric priorities invite ambiguity ("is 0 highest or lowest?").
- **Dynamic phase creation at runtime.** Phases are defined at engine construction and do not change.

### 5.7. Test Requirements

**Enable/disable**:
- A disabled system does not execute during ticks.
- An enabled system resumes execution at its original pipeline position.
- Enabling an already-enabled system is a no-op.
- Disabling an already-disabled system is a no-op.
- Referencing a non-existent system name raises a clear error.
- System names auto-derived from function names are correct.

**Phases**:
- Systems in `pre_tick` run before systems in `tick`, which run before systems in `post_tick`.
- Systems within a phase run in registration order.
- `add_system(sys)` with no phase argument places the system in `"tick"`.
- Custom phase ordering is respected.

**Variable tick rate**:
- `speed=2.0` causes `run_forever()` to sleep approximately half as long per tick.
- `speed=0.0` causes `run_forever()` to run with no sleep.
- `speed` does not affect `run(n)` or `step()`.
- `speed` does not change `dt` or any simulation values.
- Negative speed values raise an error.

### 5.8. Success Criteria

- The population demo can be extended to disable the reproduction system after tick 200 and re-enable it at tick 400, producing a visible dip and recovery in population.
- A `pre_tick` phase system can prepare data that a `tick` phase system consumes, demonstrating phase ordering.
- `run_forever()` with `speed=10.0` completes 10 seconds of simulation time in approximately 1 wall-clock second.

---

## 6. v0.3.0 -- Event Bus (Decision Required)

### 6.1. Context

The v0.1 spec explicitly forbade events:

> "Events add a second communication channel between systems. Two channels means two things to learn, two things that can go wrong, and two mental models to maintain. Shared mutable state is sufficient for a minimal engine."

This was the right call for v0.1. The question is whether the engine has outgrown this constraint.

### 6.2. The Case FOR Events

**Problem that events solve**: Direct state mutation requires systems to poll for conditions. A "damage system" applies damage by modifying a Health component. A "sound system" wants to play a sound when damage occurs. Without events, the sound system must poll Health every tick, compare to a previous value, and infer that damage happened. This is:

- **Wasteful**: Most entities were not damaged this tick.
- **Fragile**: Requires a "previous health" component or a "was damaged this tick" flag, which is itself mutable state that must be managed.
- **Indirect**: The sound system is inferring intent from state changes rather than receiving explicit notification.

Events solve this cleanly: the damage system emits a `DamageDealt` event, and the sound system listens for it.

**Additional benefits**:
- Decoupling: Systems that emit events do not need to know who consumes them.
- Debugging: An event log is a natural audit trail of what happened and why.
- Extensibility: New behavior can be added by subscribing to existing events without modifying existing systems.

### 6.3. The Case AGAINST Events

**Complexity cost**: Events introduce a second communication pathway. When debugging, you must now trace both state mutations AND event flows to understand what happened. For an educational engine, this is a meaningful tax on readability.

**Ordering questions**: When does an event handler run? Immediately when emitted (synchronous dispatch)? At the end of the tick? At the start of the next tick? Each choice has trade-offs, and the answer is not obvious. Synchronous dispatch can cause re-entrant system execution. Deferred dispatch means handlers see stale state. The "right" answer depends on the use case, which means the engine must either pick a default and document it, or support multiple modes (more complexity).

**Scope creep**: Once you have events, you want: event priorities, event cancellation, event bubbling, typed event payloads, wildcard subscriptions, event replay. Each is individually reasonable; collectively they turn a minimal engine into a framework.

**The v0.1 pattern works**: The "poll and compare" pattern is verbose but explicit. It has no hidden control flow. You can trace every state change by reading systems top to bottom. This clarity is the engine's core educational value.

### 6.4. Recommendation

**Add events, but make them opt-in and minimal.** The damage/sound example above is compelling enough to justify a basic event mechanism. BUT: the event system should be so simple that it adds almost nothing to the learning burden.

**If this recommendation is rejected**, skip to Section 6.8 (the "no events" alternative). The rest of v0.3.0 (system controls) is fully independent of this decision.

### 6.5. Proposed Design (If Approved)

**Events are fire-and-forget messages.** A system emits an event. The event is collected in a per-tick buffer. At a designated point in the tick lifecycle, all collected events are dispatched to registered handlers. Handlers run synchronously, in registration order.

**Event timing**: Events emitted during a tick are dispatched at the END of the tick, AFTER all systems in all phases have run. This avoids re-entrancy and ensures handlers see the final state of the tick. This means events are one-tick-delayed: an event emitted in tick N is handled at the end of tick N (after all systems), not during.

**Event types**: Events are plain dataclasses, just like components. No base class. If it is a dataclass, it can be an event.

**API Surface**:

- `world.emit(event)` -- Emit an event. The event is buffered, not immediately dispatched. Can be called from any system during any phase.
- `engine.on_event(EventType, handler)` -- Register a handler for a specific event type. The handler callable receives `(event, world, ctx)`.
- Event handlers are NOT systems. They do not run in the system pipeline. They run in the event dispatch phase at the end of the tick.

**Tick lifecycle with events**:

```
1. Clock advances
2. Pre-tick systems execute
3. Tick systems execute
4. Post-tick systems execute
5. Event dispatch
   - For each buffered event, in emission order:
     - For each registered handler of that event type, in registration order:
       - handler(event, world, ctx)
   - Event buffer is cleared
6. Tick completes
```

**Critical constraint**: Event handlers may NOT emit new events. If they could, you get recursive dispatch, which is exactly the complexity spiral we want to avoid. If a handler needs to cause further effects, it should mutate state, and a system in the next tick can react to that state. One level of indirection, zero levels of recursion.

### 6.6. What Events Are NOT

- NOT a pub/sub framework. No topics, no channels, no routing.
- NOT a command system. Events are notifications of things that happened, not requests for things to happen.
- NOT a replacement for direct state mutation. Events are supplementary. Simple simulations should never need them.
- NOT persistent. Events exist for one tick and are discarded. They are not part of the world's durable state. They are NOT included in snapshots.

### 6.7. Out of Scope (Even If Events Are Approved)

- Event priorities or ordering beyond registration order.
- Event cancellation or "consumed" semantics.
- Wildcard or pattern-based subscriptions.
- Event replay or event sourcing.
- Cross-tick event persistence.
- Events emitted from event handlers (explicitly forbidden).

### 6.8. Alternative: No Events (The "Stay Pure" Path)

If events are rejected, the spec should instead document the **recommended pattern for inter-system communication** via components:

**Marker components**: A system creates a short-lived "marker" component to signal that something happened. Another system queries for that marker and reacts. The marker is removed after being processed.

    Conceptually: the damage system attaches a `DamageReceived(amount=10)`
    component to the damaged entity. The sound system queries for entities
    with `DamageReceived` and plays a sound. A cleanup system in the
    `post_tick` phase removes all `DamageReceived` components.

This pattern is explicit, traceable, uses existing engine features, and requires no new API. Its downsides are verbosity and the need for a cleanup system. But it keeps the engine at zero new concepts.

**If events are rejected**: Document the marker-component pattern in a "Patterns" section of the project documentation, and consider it the official recommendation.

### 6.9. Decision Needed

The event bus design above is intentionally constrained. It adds exactly three new concepts: `emit()`, `on_event()`, and the dispatch phase. It cannot recurse, cannot persist, and cannot replace state mutation.

**The question for the project owner**: Is this minimal event system worth the conceptual overhead for an educational engine, or does the marker-component pattern suffice?

This spec proceeds as if the decision is deferred. The v0.3.0 implementation can ship system controls alone, with the event bus as an optional addition in v0.3.1 or later, depending on the answer.

---

## 7. File Structure Changes

### 7.1. v0.1.1

No new files. Changes are limited to:

- `tick/world.py` -- Add alive-entity guards.
- `tick/types.py` -- Add `DeadEntityError` (or a new `tick/errors.py` -- implementer's choice, but keeping it in `types.py` avoids adding a file for a single class).
- `tick/__init__.py` -- Export `DeadEntityError`.
- `tests/test_world.py` -- Add guard tests.

### 7.2. v0.2.0

New and modified files:

- `tick/types.py` -- Extend `TickContext` with `random` field.
- `tick/clock.py` -- Accept and thread through `Random` instance.
- `tick/engine.py` -- Add `seed` parameter, `snapshot()`, `restore()`.
- `tick/world.py` -- Add `snapshot()`, `restore()`, component registry.
- `tick/serialize.py` (new) -- Snapshot creation and restoration logic, kept separate from world/engine to maintain single-responsibility.
- `tests/test_rng.py` (new) -- Seed-able RNG tests.
- `tests/test_serialize.py` (new) -- Serialization round-trip tests.
- `examples/replay.py` (new) -- Snapshot and replay demo.

### 7.3. v0.3.0

New and modified files:

- `tick/engine.py` -- System enable/disable, phases, speed multiplier.
- `tick/pipeline.py` (new) -- Phase-aware system pipeline (extracted from engine to manage complexity).
- `tick/events.py` (new, conditional) -- Event bus, only if events are approved.
- `tests/test_pipeline.py` (new) -- Phase and enable/disable tests.
- `tests/test_events.py` (new, conditional) -- Event bus tests.

---

## 8. Dependency Policy

### 8.1. v0.1.1

No new dependencies. Stdlib only.

### 8.2. v0.2.0

No new dependencies. `random.Random` and `dataclasses` are stdlib. JSON serialization is the user's concern (stdlib `json` is sufficient but not required by the engine).

### 8.3. v0.3.0

No new dependencies anticipated. All features are implementable with stdlib.

### 8.4. General Policy (v0.2+)

The v0.1 constraint of "zero external dependencies" is relaxed but not abandoned. The engine should remain installable with `pip install tick` and no extras. External dependencies are acceptable only if they provide substantial value that cannot be reasonably achieved with stdlib (e.g., a future performance-critical feature might justify numpy). The bar is high. For v0.2.0 and v0.3.0, no external dependencies are needed.

---

## 9. Backward Compatibility Summary

| Change | Breaks v0.1 code? | Migration |
|--------|--------------------|-----------|
| `attach()` raises on dead entity | Only buggy code | Add `alive()` guard |
| `get()` raises `DeadEntityError` instead of `KeyError` | No -- `DeadEntityError` extends `KeyError` | None |
| `has()` returns `False` for dead entity | No -- same behavior, different implementation | None |
| `TickContext` gains `random` field | No -- named access is compatible | None |
| `engine.snapshot()` / `engine.restore()` | No -- new methods | None |
| `add_system()` gains optional `name` and `phase` params | No -- defaults match v0.1 behavior | None |
| `engine.speed` property | No -- new property | None |
| `world.emit()` (if events approved) | No -- new method | None |

---

## 10. Release Sequence and Milestones

### v0.1.1 -- Guard Rails

- Estimated scope: ~20 lines of implementation changes, ~40 lines of new tests.
- Release as a hotfix branch from main.
- Merge to main and develop.

### v0.2.0 -- Replay

- Implement seed-able RNG first (simpler, fewer moving parts).
- Implement serialization second (depends on RNG for full replay).
- New example demonstrating snapshot + replay.
- Release as a feature branch from develop.

### v0.3.0 -- Control

- Implement system enable/disable first (smallest change to engine loop).
- Implement phases second (refactors the pipeline).
- Implement variable tick rate third (pacing change, independent of pipeline).
- Event bus is a separate decision; if approved, implement last.
- Release as a feature branch from develop.

---

## 11. Resolved Questions

1. **Event bus**: Yes, opt-in. Ships in v0.3.0 per Section 6.5 design.
2. **TickContext implementation**: Switch to frozen dataclass in v0.2.0 when adding `ctx.random`.
3. **Snapshot format stability**: Public API with version field. No cross-version guarantee until v1.0.
4. **System removal**: No `remove_system()`. `disable_system()` is sufficient.
5. **Speed multiplier range**: No upper bound. Document the behavior.

---

## References

- SPEC.md (v0.1) -- the foundation this document builds on.
- Python `random.Random` -- stdlib seeded RNG, supports `getstate()` / `setstate()`.
- Python `dataclasses.asdict()` -- recursive dataclass-to-dict conversion.
- [esper](https://github.com/benmoran56/esper) -- Python ECS reference. Supports `components_for_entity()` for entity transfer between worlds, conceptually similar to our snapshot approach.
- Robert Nystrom, [Game Loop](https://gameprogrammingpatterns.com/game-loop.html) -- variable timestep discussion.
- Robert Nystrom, [Event Queue](https://gameprogrammingpatterns.com/event-queue.html) -- deferred event dispatch pattern, influenced Section 6.5.
