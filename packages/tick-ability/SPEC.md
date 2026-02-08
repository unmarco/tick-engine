# tick-ability v0.1.0 -- Technical Specification

**Version**: 0.1.0
**Date**: 2026-02-08
**Status**: Draft
**Author**: W72 Spec Writer

---

## 1. What This Is

`tick-ability` models **player-triggered abilities** -- on-demand activated effects with charges, cooldowns, and duration-based effect pipelines. Where `tick-event` handles things that happen TO the simulation (probabilistic, per-tick evaluation), `tick-ability` handles things that ACT ON the simulation (explicit invocation by the player or an AI actor).

Abilities are miracles, spells, powers, policy levers, hero ultimates -- anything an actor *can do* on command, constrained by charges, cooldowns, conditions, and optional resource costs.

**One sentence**: A registry of invocable abilities with charge tracking, per-use cooldowns, and duration-based effect callbacks that integrates with the tick engine's system pipeline.

---

## 2. Relationship to tick-event

tick-event and tick-ability are structurally similar (both manage named effects with duration, cooldown, and callbacks) but differ in trigger semantics:

| Concern | tick-event | tick-ability |
|---|---|---|
| Trigger | Automatic, per-tick probability roll | Explicit `invoke()` call |
| Evaluation | Every tick, all inactive events checked | Only when caller requests |
| Charges | N/A (infinite re-fire) | Finite charges, optional regen |
| Probability | Per-event `probability` field | N/A (deterministic invoke) |
| Cycles | Phase-based repeating cycles | N/A |
| Cost | N/A | Optional resource cost callback |
| Guards | EventGuards registry | AbilityGuards registry (same pattern) |

tick-ability is an **optional dependency** on tick-event. It works standalone but CAN integrate with `EventScheduler` if the user wants abilities to interact with world-level events (e.g., "this ability can only fire during winter").

The dependency direction is:

```
tick >= 0.2.1  (required)
tick-event >= 0.1.0  (optional, for EventScheduler integration)
```

---

## 3. Core Concepts

### AbilityDef

A static definition of what an ability is. Registered once, never mutated at runtime. Analogous to `EventDef` in tick-event.

Fields:

- **name** -- Unique identifier string (e.g., `"bless_harvest"`, `"fireball"`, `"freeze_wave"`)
- **duration** -- How many ticks the effect lasts once invoked. Fixed integer or `(min, max)` tuple for random range (resolved via `ctx.random` on invocation, same pattern as `EventDef.duration`). A duration of `0` means the ability is instantaneous -- `on_start` fires, `on_end` fires immediately on the same tick, no `on_tick` calls.
- **cooldown** -- Minimum ticks between uses. Starts counting after the effect ends (not after invocation). `0` means no cooldown.
- **max_charges** -- Maximum number of charges this ability can hold. `1` is a simple single-use-then-cooldown pattern. Higher values allow burst usage. `-1` means unlimited charges (no charge tracking).
- **charge_regen** -- Ticks between charge regeneration. `0` means charges do not regenerate. When a charge is consumed and `charge_regen > 0`, the regen timer begins. One charge is restored each time the timer fires. Charges cap at `max_charges`.
- **conditions** -- List of guard name strings. ALL must pass for invocation to succeed. Same pattern as `EventDef.conditions`.

### AbilityState

Runtime state of a single ability. Mutable, serializable. Tracks everything that changes between ticks.

Fields:

- **name** -- Matches the `AbilityDef.name`
- **charges** -- Current charge count
- **cooldown_remaining** -- Ticks remaining until ability is off cooldown. `0` means ready.
- **active_remaining** -- Ticks remaining on the current active effect. `0` means not active.
- **active_started_at** -- Tick number when current effect was invoked. `-1` if not active.
- **regen_remaining** -- Ticks until next charge regenerates. `0` means regen not in progress.

### AbilityManager

The central manager. Owns definitions and runtime states. Provides `invoke()`, queries, and serialization. Analogous to `EventScheduler` in tick-event, but with explicit invocation instead of automatic evaluation.

### AbilityGuards

A registry mapping guard name strings to callable predicates. Same pattern as `EventGuards` in tick-event. Signature: `(World, AbilityManager) -> bool`.

### System Factory

`make_ability_system()` returns a `(World, TickContext) -> None` callable that processes ability state each tick: decrements active effects, handles expiry, decrements cooldowns, regenerates charges.

---

## 4. Architecture

```
+------------------------------------------------------+
|                   AbilityManager                      |
|                                                       |
|  +---------------+   +-----------------+              |
|  |  AbilityDef   |   |  AbilityState   |              |
|  |  (definitions)|   |  (runtime)      |              |
|  |               |   |                 |              |
|  | name          |   | charges         |              |
|  | duration      |   | cooldown_rem    |              |
|  | cooldown      |   | active_rem      |              |
|  | max_charges   |   | regen_rem       |              |
|  | charge_regen  |   |                 |              |
|  | conditions    |   |                 |              |
|  +---------------+   +-----------------+              |
|                                                       |
|  invoke(name, world, ctx) -> bool                     |
|  is_available(name, world) -> bool                    |
|  is_active(name) -> bool                              |
|  charges(name) -> int                                 |
|  time_remaining(name) -> int                          |
|  cooldown_remaining(name) -> int                      |
|  snapshot() -> dict                                   |
|  restore(data) -> None                                |
+------------------------------------------------------+

+------------------------------------------------------+
|                   AbilityGuards                       |
|                                                       |
|  register(name, fn) -> None                           |
|  check(name, world, manager) -> bool                  |
+------------------------------------------------------+

+------------------------------------------------------+
|               make_ability_system()                   |
|                                                       |
|  Each tick:                                           |
|    1. Decrement active effects, end expired (on_end)  |
|    2. Tick still-active effects (on_tick)              |
|    3. Decrement cooldowns                             |
|    4. Regenerate charges                              |
+------------------------------------------------------+
```

---

## 5. Module Layout

```
packages/tick-ability/
    tick_ability/
        __init__.py       -- Public API re-exports
        types.py          -- AbilityDef, AbilityState (dataclasses)
        manager.py        -- AbilityManager (registration, invocation, queries)
        guards.py         -- AbilityGuards (condition predicates)
        systems.py        -- make_ability_system() factory
    tests/
        __init__.py
        test_types.py     -- AbilityDef/AbilityState construction
        test_manager.py   -- Define, invoke, charges, cooldowns, queries
        test_guards.py    -- Guard registration and checking
        test_system.py    -- System factory, tick processing, callbacks
        test_integration.py -- Multi-ability scenarios, snapshot/restore
    pyproject.toml
```

**Target**: ~250 lines of implementation code across the four modules.

---

## 6. API Surface

### 6.1 types.py -- Data Types

#### AbilityDef

A frozen definition of an ability. Registered with `AbilityManager.define()`. Not serialized (re-registered after restore, same pattern as `EventDef`).

Fields:
- `name: str` -- unique identifier
- `duration: int | tuple[int, int]` -- effect duration in ticks, fixed or random range
- `cooldown: int` -- ticks after effect ends before re-use (default `0`)
- `max_charges: int` -- maximum charges (default `1`, `-1` for unlimited)
- `charge_regen: int` -- ticks between charge regeneration (default `0`, meaning no regen)
- `conditions: list[str]` -- guard names, ALL must pass (default empty)

#### AbilityState

Runtime state for one ability. Mutable, serializable. Managed internally by `AbilityManager`.

Fields:
- `name: str` -- matches `AbilityDef.name`
- `charges: int` -- current available charges
- `cooldown_remaining: int` -- ticks until off cooldown (default `0`)
- `active_remaining: int` -- ticks remaining on current effect (default `0`)
- `active_started_at: int` -- tick number of last invocation (default `-1`)
- `regen_remaining: int` -- ticks until next charge regeneration (default `0`)

### 6.2 manager.py -- AbilityManager

Standalone manager class. No dependency on World or Engine at construction time. Analogous to `EventScheduler`.

#### Constructor

`AbilityManager()` -- no arguments. Initializes empty definitions and states.

#### Registration

**`define(ability: AbilityDef) -> None`**

Register an ability definition. Initializes the corresponding `AbilityState` with charges set to `max_charges` (or `0` if `max_charges` is `-1`, since unlimited means charges are not tracked). Insertion order is preserved (for deterministic iteration). Re-defining an ability with the same name overwrites the definition but preserves the existing runtime state.

**`definition(name: str) -> AbilityDef | None`**

Look up an ability definition by name. Returns `None` if not defined.

#### Invocation

**`invoke(name: str, world: World, ctx: TickContext, guards: AbilityGuards | None = None) -> bool`**

Attempt to invoke an ability. Returns `True` if invocation succeeded, `False` if blocked by any of:

1. **Unknown ability** -- name not registered
2. **Already active** -- effect is currently running (`active_remaining > 0`)
3. **On cooldown** -- `cooldown_remaining > 0`
4. **No charges** -- `charges == 0` (and `max_charges != -1`)
5. **Guard failure** -- any condition in `AbilityDef.conditions` returns `False`

If all checks pass:
1. Consume one charge (if `max_charges != -1`)
2. Resolve duration (fixed or random via `ctx.random`)
3. Set `active_remaining` to resolved duration
4. Set `active_started_at` to `ctx.tick_number`
5. If `charge_regen > 0` and charges are below max and regen is not already running, start regen timer (`regen_remaining = charge_regen`)
6. Return `True`

**Important**: `invoke()` only sets state. It does NOT call `on_start`. The system factory's tick processing handles all callbacks. This means if `invoke()` is called mid-tick (from within a system), the `on_start` callback fires on the **next** tick when the ability system processes it. This avoids re-entrancy issues and keeps callback timing predictable.

**Design decision -- invoke sets state, system fires callbacks**: This is the critical difference from a pattern where `invoke()` directly calls `on_start`. By separating invocation (state mutation) from callback execution (system processing), we get:
- Predictable callback ordering (always during the ability system's slot in the pipeline)
- No re-entrancy (callbacks cannot trigger during another system's execution)
- Snapshot consistency (state is always coherent between ticks)

The trade-off is a 1-tick delay between invocation and `on_start`. For instantaneous abilities (`duration=0`), this means `on_start` and `on_end` both fire on the tick after invocation, not the tick of invocation.

#### Queries

**`is_available(name: str, world: World, guards: AbilityGuards | None = None) -> bool`**

Can this ability be invoked right now? Checks: defined, not active, not on cooldown, has charges (if tracked), all guards pass. Does NOT consume charges or change state -- purely informational.

**`is_active(name: str) -> bool`**

Is this ability's effect currently running? (`active_remaining > 0`)

**`charges(name: str) -> int`**

Current charge count. Returns `-1` if ability has unlimited charges. Raises `KeyError` if ability not defined.

**`time_remaining(name: str) -> int`**

Remaining ticks on the active effect. `0` if not active. Raises `KeyError` if not defined.

**`cooldown_remaining(name: str) -> int`**

Remaining ticks on cooldown. `0` if not on cooldown. Raises `KeyError` if not defined.

**`state(name: str) -> AbilityState | None`**

Direct access to the runtime state for a given ability. Returns `None` if not defined.

**`defined_abilities() -> list[str]`**

List all defined ability names in definition order.

#### Serialization

**`snapshot() -> dict`**

Serialize all runtime state (not definitions). Returns a JSON-compatible dict.

Format:
```
{
    "abilities": [
        {
            "name": "fireball",
            "charges": 2,
            "cooldown_remaining": 0,
            "active_remaining": 3,
            "active_started_at": 42,
            "regen_remaining": 5
        },
        ...
    ]
}
```

**`restore(data: dict) -> None`**

Restore runtime state from a snapshot dict. Definitions must be re-registered first (same pattern as `EventScheduler.restore()`). Clears existing runtime state before restoring.

### 6.3 guards.py -- AbilityGuards

Identical pattern to `EventGuards` in tick-event. Maps guard name strings to callable predicates.

**`AbilityGuards()`** -- no arguments.

**`register(name: str, fn: Callable[[World, AbilityManager], bool]) -> None`**

Register a named guard predicate. Overwrites if already registered.

**`check(name: str, world: World, manager: AbilityManager) -> bool`**

Evaluate a guard. Raises `KeyError` if not registered.

**`has(name: str) -> bool`**

Check if a guard name is registered.

**`names() -> list[str]`**

List all registered guard names.

### 6.4 systems.py -- System Factory

**`make_ability_system(manager, guards, on_start, on_end, on_tick) -> Callable[[World, TickContext], None]`**

Parameters:
- `manager: AbilityManager` -- the manager instance to process
- `guards: AbilityGuards | None` -- optional guards (only needed if `invoke()` is called without passing guards directly; the system itself does not evaluate guards -- invocation does)
- `on_start: Callable[[World, TickContext, str], None] | None` -- called when a newly-invoked ability is first processed by the system
- `on_end: Callable[[World, TickContext, str], None] | None` -- called when an active effect expires
- `on_tick: Callable[[World, TickContext, str, int], None] | None` -- called each tick for active effects (receives ability name and remaining ticks)

The returned system processes abilities each tick in the following order:

```
1. Process newly-invoked abilities
   - For each ability where active_remaining > 0 and this is the
     first system tick since invocation:
     - Call on_start(world, ctx, name)
   - For instantaneous abilities (duration=0):
     - Call on_start then immediately on_end
     - Set active_remaining = 0, active_started_at = -1
     - Begin cooldown if defined

2. Decrement active effects
   - For each ability with active_remaining > 0 (non-instantaneous):
     - Decrement active_remaining by 1
     - If active_remaining reaches 0:
       - Call on_end(world, ctx, name)
       - Set active_started_at = -1
       - Begin cooldown (cooldown_remaining = AbilityDef.cooldown)

3. Tick still-active effects
   - For each ability still active after decrement:
     - Call on_tick(world, ctx, name, active_remaining)

4. Decrement cooldowns
   - For each ability with cooldown_remaining > 0:
     - Decrement by 1

5. Regenerate charges
   - For each ability with regen_remaining > 0:
     - Decrement regen_remaining by 1
     - If regen_remaining reaches 0 and charges < max_charges:
       - Restore one charge
       - If charges still < max_charges: restart regen timer
```

#### Detecting "newly invoked" abilities

The system needs to distinguish between "first tick of a new invocation" and "continuing an active effect". The mechanism: the system tracks a set of ability names it has already started (`_started` set, internal to the closure). When it sees `active_remaining > 0` and the name is NOT in `_started`, it fires `on_start` and adds it to `_started`. When the effect ends (`active_remaining` reaches 0), the name is removed from `_started`.

This is an implementation detail (the closure captures a mutable set), but it is specified here because it affects observable behavior: `on_start` fires exactly once per invocation, on the first system tick after `invoke()`.

---

## 7. Tick Lifecycle Detail

A complete example of ability timing over multiple ticks.

Given: `AbilityDef(name="shield", duration=3, cooldown=2, max_charges=2, charge_regen=4)`

```
Tick 0: (setup)
  State: charges=2, cooldown=0, active=0, regen=0

User calls invoke("shield") during tick 1 (from some other system)
  invoke() sets: charges=1, active=3, started_at=1, regen=4

Tick 2: ability system processes
  Step 1: "shield" is newly invoked (not in _started set)
    -> on_start("shield") fires
    -> Add "shield" to _started
  Step 2: Decrement active: 3 -> 2
  Step 3: on_tick("shield", 2) fires
  Step 5: Regen: 4 -> 3
  State: charges=1, cooldown=0, active=2, regen=3

Tick 3:
  Step 2: Decrement active: 2 -> 1
  Step 3: on_tick("shield", 1) fires
  Step 5: Regen: 3 -> 2
  State: charges=1, cooldown=0, active=1, regen=2

Tick 4:
  Step 2: Decrement active: 1 -> 0 -> EXPIRED
    -> on_end("shield") fires
    -> Remove "shield" from _started
    -> Begin cooldown: cooldown_remaining = 2
  Step 4: Decrement cooldown: 2 -> 1
  Step 5: Regen: 2 -> 1
  State: charges=1, cooldown=1, active=0, regen=1

Tick 5:
  Step 4: Decrement cooldown: 1 -> 0
  Step 5: Regen: 1 -> 0 -> charge restored: charges=2
    -> charges == max_charges, regen stops
  State: charges=2, cooldown=0, active=0, regen=0

Tick 5+: "shield" is available again (charges=2, no cooldown)
```

### Instantaneous Abilities (duration=0)

```
Given: AbilityDef(name="smite", duration=0, cooldown=5, max_charges=3)

User calls invoke("smite") during tick 1
  invoke() sets: charges=2, active=0, started_at=1

Tick 2: ability system processes
  Step 1: "smite" has active_remaining=0 but active_started_at != -1
    -> This is an instantaneous ability (detected by duration=0 in def)
    -> on_start("smite") fires
    -> on_end("smite") fires immediately
    -> Set active_started_at = -1
    -> Begin cooldown: cooldown_remaining = 5
  Step 4: Decrement cooldown: 5 -> 4
```

**Detecting instantaneous**: For instantaneous abilities, `invoke()` sets `active_started_at` to the tick number but leaves `active_remaining` at `0`. The system detects this state (`active_started_at != -1` AND `active_remaining == 0`) and treats it as a zero-duration invocation.

---

## 8. Invocation Rejection Reasons

When `invoke()` returns `False`, the caller may want to know why. For v0.1.0, the boolean return is sufficient. A future version could return an enum or raise a specific exception.

Rejection priority (checked in this order):
1. Not defined
2. Currently active
3. On cooldown
4. No charges
5. Guard condition failed

This ordering means the most "permanent" blockers are checked first. A user can check `is_available()` before invoking to get the same answer without side effects.

---

## 9. tick-event Integration (Optional)

If tick-event is available, abilities can reference `EventScheduler` state in their guard conditions. This is NOT a code dependency -- it works through the guard system.

Example usage pattern (described, not coded):

A guard named `"is_winter"` checks whether the "winter" cycle phase is active in an `EventScheduler`. The guard function closes over the scheduler instance. The ability `"blizzard"` lists `"is_winter"` in its conditions. When the user tries to invoke `"blizzard"`, the guard checks `scheduler.is_active("winter")`.

This works because `AbilityGuards` predicates have signature `(World, AbilityManager) -> bool`, but the closure can capture any external state (same pattern as tick-event guards capturing external state).

No import of `tick_event` is needed in `tick_ability` itself. The integration is purely at the user's application level through closures.

---

## 10. Snapshot / Restore

### Snapshot Format

The `AbilityManager.snapshot()` output is a JSON-compatible dict containing all runtime state:

```
{
    "abilities": [
        {
            "name": "shield",
            "charges": 1,
            "cooldown_remaining": 0,
            "active_remaining": 2,
            "active_started_at": 42,
            "regen_remaining": 3
        }
    ]
}
```

### Restore Contract

1. Definitions must be re-registered via `define()` before calling `restore()`. Definitions are not serialized (they are code-level configuration, same as `EventDef` and `CycleDef`).
2. `restore()` clears all existing runtime state before applying the snapshot.
3. The system factory's internal `_started` set must be rebuilt from the restored state: any ability with `active_remaining > 0` should be added to `_started` so that `on_start` does NOT re-fire for effects that were already in progress before the snapshot.
4. If a snapshot contains an ability name not in the current definitions, it is silently skipped (forward compatibility).

### System State Reconstruction

The `make_ability_system()` factory should accept the manager and reconstruct its `_started` set from the manager's current state after a restore. This means `_started` is populated with names of all abilities where `active_remaining > 0` OR `active_started_at != -1`.

Concretely: after the user calls `manager.restore(data)`, the next tick of the ability system should NOT fire `on_start` for abilities that were already mid-effect. It should continue to fire `on_tick` and eventually `on_end` as the remaining duration counts down.

---

## 11. Project Configuration

### pyproject.toml

Package name: `tick-ability`
Import name: `tick_ability`
Version: `0.1.0`
Python: `>=3.11`
Dependencies: `tick>=0.2.1` (only)
Build system: hatchling
Workspace source: `tick = { workspace = true }`
Test paths: `["tests"]`
Wheel packages: `["tick_ability"]`

tick-event is NOT listed as a dependency. Integration with tick-event is done at the application level via guard closures.

### __init__.py Exports

```
AbilityDef, AbilityState       -- from tick_ability.types
AbilityManager                  -- from tick_ability.manager
AbilityGuards                   -- from tick_ability.guards
make_ability_system             -- from tick_ability.systems
```

---

## 12. Use Case Examples

These are conceptual descriptions of how tick-ability would be used in different scenarios.

### Colony / God-Game: Divine Miracles

The player has a set of divine powers: Bless Harvest (boosts food production for 20 ticks), Smite Raiders (instant damage to all raiders), Shield from Plague (prevents plague event for 30 ticks). Each has limited charges that regenerate over time. The player invokes them via UI buttons. The system callbacks modify world state (boost modifiers, destroy raider entities, set plague-immunity flags).

### Roguelike: Consumable Scrolls

Each scroll type is an AbilityDef with `max_charges=1` and `charge_regen=0`. Using a scroll consumes the charge permanently. Abilities like Scroll of Fireball (`duration=0`, instant damage) or Scroll of Invisibility (`duration=50`, grants stealth component for 50 ticks).

### Tower Defense: Special Powers

Player powers with cooldowns: Freeze Wave (`duration=10`, `cooldown=60`), Damage Burst (`duration=0`, `cooldown=30`). The system callbacks apply slow effects to enemies or deal area damage. Guards can enforce conditions like "at least 5 enemies on screen".

### Autobattler: Hero Ultimates

Each hero has one ultimate with `max_charges=1` and `charge_regen=30` (charges during combat). Ultimates have varying durations. A guard condition could require "hero has > 50% HP". The system callbacks apply powerful effects.

---

## 13. Edge Cases and Design Decisions

### Invoking while active

Rejected. An ability cannot be invoked while its effect is already running. The user must wait for the effect to expire (and any cooldown to finish). This prevents stacking of the same ability.

Rationale: Stacking introduces significant complexity (multiple active instances, independent countdowns, overlapping callbacks). If a user needs stacking, they can define multiple abilities (`"shield_1"`, `"shield_2"`) or use a different mechanism.

### Invoking during the ability system's tick

If another system that runs BEFORE the ability system calls `invoke()`, the ability system will process it in the same tick (fire `on_start`, start countdown). If a callback from the ability system itself calls `invoke()` on a different ability, that invocation sets state but the newly-invoked ability will NOT be processed until the next tick (to avoid re-entrancy within the ability system's own processing loop).

Implementation guidance: The system should iterate over a snapshot of ability names at the start of its processing, not a live list. Abilities invoked during callback execution are picked up next tick.

### Zero charges with unlimited setting

When `max_charges=-1`, the `charges` field in `AbilityState` is meaningless and should be `0`. The charge check is skipped entirely. `manager.charges("name")` returns `-1` to indicate unlimited.

### Regen while active

Charge regeneration proceeds independently of whether the ability is active. A player could invoke an ability, and while the effect is running, charges regenerate. This allows patterns like "use 2 charges quickly, then wait for the effect to expire and charges to regen before using again".

### Cooldown stacking with regen

Cooldown and charge regen are independent timers. Both tick down simultaneously. An ability could finish its cooldown while still waiting for charge regen, or vice versa. The ability is available only when BOTH `cooldown_remaining == 0` AND `charges > 0` (or unlimited).

### Regen timer start

The regen timer starts when `invoke()` consumes a charge AND charges drop below `max_charges` AND regen is not already running (`regen_remaining == 0`). If regen is already counting down (from a previous charge consumption), the existing timer continues -- invoking again does NOT reset the regen timer.

### Multiple abilities active simultaneously

Multiple different abilities can be active at the same time. There is no mutual exclusion between different abilities. If the user needs exclusion, they can implement it via guards (e.g., a guard that checks `not manager.is_active("other_ability")`).

### Definition order and processing order

Abilities are processed in definition order within the system, matching tick-event's pattern. `defined_abilities()` returns names in insertion order. This makes behavior deterministic.

---

## 14. Testing Strategy

### test_types.py (~10 tests)

- AbilityDef construction with defaults
- AbilityDef with random duration range
- AbilityState construction with defaults
- AbilityState mutability

### test_manager.py (~25 tests)

- `define()` registers ability and initializes state
- `define()` with unlimited charges (`max_charges=-1`)
- `define()` preserves insertion order
- `definition()` returns None for unknown
- `invoke()` succeeds and consumes charge
- `invoke()` fails when not defined
- `invoke()` fails when active
- `invoke()` fails when on cooldown
- `invoke()` fails when no charges
- `invoke()` fails when guard blocks
- `invoke()` with unlimited charges does not decrement
- `invoke()` starts regen timer on charge consumption
- `invoke()` does not restart regen timer if already running
- `invoke()` with random duration resolves deterministically
- `is_available()` reflects all blocking conditions
- `is_active()` correctness
- `charges()` returns current count
- `charges()` returns -1 for unlimited
- `time_remaining()` correctness
- `cooldown_remaining()` correctness
- `state()` returns AbilityState or None
- `defined_abilities()` returns names in order
- `snapshot()` round-trip
- `restore()` clears previous state
- `restore()` skips unknown ability names

### test_guards.py (~6 tests)

- Register and check a guard
- Overwrite a guard
- KeyError on unknown guard
- `has()` correctness
- `names()` lists all
- Guard receives correct arguments

### test_system.py (~20 tests)

- `on_start` fires on first tick after invoke
- `on_end` fires when effect expires
- `on_tick` fires each tick while active
- Instantaneous ability (`duration=0`): `on_start` + `on_end` same tick
- Cooldown begins after effect ends
- Cooldown decrements each tick
- Charge regen decrements each tick
- Charge restored when regen timer fires
- Regen stops when charges reach max
- Multiple abilities processed in definition order
- No `on_start` re-fire after restore (mid-effect)
- Callbacks receive correct arguments
- Ability invoked during callback is deferred to next tick

### test_integration.py (~10 tests)

- Full engine integration: define, invoke, run N ticks, verify state
- Multiple abilities with interleaved invocations
- Snapshot/restore mid-effect, verify continuity
- Deterministic behavior with seeded RNG
- Guard integration with external state

**Target**: ~70 tests total.

---

## 15. What Is Explicitly Out of Scope (v0.1.0)

| Concern | Why it is out |
|---|---|
| Ability stacking / multiple instances | Adds significant complexity. Use multiple definitions if needed. |
| Ability upgrades / leveling | Domain-specific. Implement by redefining with new parameters. |
| Ability combos / chains | Implement via guards and callbacks at the application level. |
| Targeting (entity or position) | Domain-specific. Callbacks receive `(world, ctx, name)` -- targeting is the callback's job. |
| Mana / resource cost enforcement | The guard system handles this. A guard can check resource availability. |
| Animation / visual timing | No visual output. |
| Ability inheritance / composition | Use helper functions to construct similar AbilityDefs. |
| Per-entity abilities | AbilityManager is world-level, not per-entity. For per-entity abilities, the user manages one AbilityManager per entity or uses a component-based approach. |
| Rejection reason enum | `invoke()` returns bool. A future version could return detailed rejection info. |
| tick-event as hard dependency | Integration is via closures at the application level. |

---

## 16. Future Considerations (Post v0.1.0)

These are NOT part of the v0.1.0 spec but inform design decisions to avoid painting into a corner.

- **Per-entity ability components**: An `Abilities` component attached to entities, with an entity-scoped ability system. Would require a different data model (component-based state instead of manager-based).
- **Ability groups / categories**: Mutual exclusion groups, shared cooldowns across a category.
- **Invoke rejection reasons**: Return a `Reason` enum instead of `bool` from `invoke()`.
- **Cost callbacks**: A `cost` callback on `AbilityDef` that is called during invocation to deduct resources. Currently achievable via guards (check) + `on_start` callback (deduct).
- **Charge regen scaling**: Variable regen rates based on conditions.
- **Buff/debuff integration with tick-schedule**: Using `Timer` components for ability effects instead of the built-in duration tracking.

---

## 17. Verification Criteria

The package is complete when:

1. `uv run --package tick-ability pytest` -- all tests pass
2. `AbilityManager` round-trips through `snapshot()`/`restore()` cleanly
3. All callbacks (`on_start`, `on_end`, `on_tick`) fire at the correct ticks
4. Instantaneous abilities (`duration=0`) work correctly
5. Charge regeneration and cooldown timers are independent and correct
6. Guard conditions block invocation as expected
7. Integration with tick engine is demonstrated (engine + ability system + invoke)
8. Total implementation code is under 300 lines
9. Zero external dependencies
10. mypy strict mode passes

---

## 18. Open Questions

1. **Should `invoke()` call `on_start` immediately instead of deferring?** The current spec defers to the system tick for predictability. The trade-off is a 1-tick delay. For fast-paced simulations at high TPS this is negligible, but for turn-based games with 1 TPS it means a full turn delay. Resolution: v0.1.0 uses deferred callbacks. If immediate callbacks prove necessary, they can be added as an option in v0.2.0.

2. **Should the system factory accept `manager` as a parameter or should `AbilityManager` contain the system?** The current spec follows tick-event's pattern (factory takes manager as parameter). This keeps the manager decoupled from the system pipeline. Resolution: follow tick-event pattern.

3. **Should `AbilityGuards` be a separate class or merged with `EventGuards`?** They are identical in structure. However, keeping them separate means tick-ability has no dependency on tick-event. Resolution: separate class, identical API. A future shared base module could unify them.

---

## References

- `tick-event` v0.1.0 -- Direct inspiration for manager/system/guards pattern
- `tick-schedule` v0.1.0 -- Timer/Periodic component pattern
- `tick` v0.2.1 -- Core engine API (World, TickContext, Engine)
- Ability system patterns from: Dota 2, League of Legends, Slay the Spire, Dwarf Fortress
