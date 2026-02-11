# tick-colony

Reusable colony builder and roguelike simulation primitives for the tick engine. Integrates 11 extension packages and provides needs, stats with modifiers, containment, lifecycle, event logging, and a unified snapshot/restore coordinator.

## Install

```bash
pip install tick-colony
```

```python
import tick_colony
```

## Adopted Extensions

tick-colony re-exports the public APIs of all extension packages (including tick-ai and tick-llm) so colony users can import everything from one place:

| Package | Re-exports |
|---------|------------|
| tick-spatial | `Grid2D`, `Pos2D`, `pathfind`, `make_spatial_cleanup_system` |
| tick-schedule | `Timer`, `make_timer_system` |
| tick-fsm | `FSM`, `FSMGuards`, `make_fsm_system` |
| tick-blueprint | `BlueprintRegistry` |
| tick-signal | `SignalBus` |
| tick-event | `EventScheduler`, `EventGuards`, `EventDef`, `CycleDef`, `make_event_system` |
| tick-command | `CommandQueue`, `make_command_system`, `expand_footprint`, `resolve_footprint` |
| tick-atlas | `CellDef`, `CellMap` |
| tick-ability | `AbilityDef`, `AbilityState`, `AbilityGuards`, `AbilityManager`, `make_ability_system` |
| tick-resource | `Inventory`, `InventoryHelper`, `Recipe`, `ResourceDef`, `ResourceRegistry`, `can_craft`, `craft`, `make_resource_decay_system` |
| tick-ai | `AIManager`, `BehaviorTree`, `Blackboard`, `UtilityAgent`, `Status`, `Node`, `make_bt_system`, `make_utility_system` |
| tick-llm | `LLMAgent`, `LLMClient`, `LLMConfig`, `LLMManager`, `MockClient`, `make_llm_system` |

## LLM Integration (0.4.0+)

Colony-specific context builders, directive parsers, and a pressure system for LLM-driven strategic gameplay:

| Module | Exports | Description |
|--------|---------|-------------|
| `context` | `make_resource_context`, `make_population_context`, `make_spatial_context`, `make_event_context`, `make_colony_context` | Context builder factories for LLM prompt assembly |
| `directive` | `make_directive_parser`, `DirectiveHandler` | Structured directive parsing from LLM JSON responses |
| `pressure` | `make_pressure_system`, `PressureThresholds` | Pressure monitor that resets LLM cooldowns on significant state changes |

The chronicle demo (`examples/chronicle.py`) showcases 4 LLM agents (Steward, Builder, Warden, Narrator) with MockClient and real LLM endpoint support:

```bash
uv run --package tick-colony python -m examples.chronicle --mock       # deterministic mock
uv run --package tick-colony python -m examples.chronicle --llm        # real LLM endpoint
uv run --package tick-colony python -m examples.chronicle --no-llm     # original behavior
```

## Colony Components

| Component | Fields | Description |
|-----------|--------|-------------|
| `NeedSet` | `data: dict` | Collection of needs (hunger, fatigue, etc.) |
| `StatBlock` | `data: dict[str, float]` | Base stat values |
| `Modifiers` | `entries: list` | Temporary stat bonuses with duration |
| `Container` | `items: list[int], capacity: int` | Holds child entity IDs (hierarchy) |
| `ContainedBy` | `parent: int` | Marks entity as inside a container |
| `Lifecycle` | `born_tick: int, max_age: int` | Age tracking, auto-despawn |
| `Inventory` | `slots: dict[str, int], capacity: int` | Typed resource quantities |

## Framework Objects

| Class | Description |
|-------|-------------|
| `EventLog(max_entries=0)` | Ring-buffer event log with emit/query/last |
| `ColonySnapshot(grid, event_log, scheduler, cellmap, ability_manager, resource_registry)` | Unified snapshot/restore coordinator (all params optional) |

## System Factories

| Factory | Description |
|---------|-------------|
| `make_need_decay_system(on_critical, on_zero)` | Decays needs each tick |
| `make_modifier_tick_system()` | Decrements modifier durations, removes expired |
| `make_lifecycle_system(on_death)` | Despawns entities that exceed max_age |

## Helpers

| Function | Description |
|----------|-------------|
| `register_colony_components(world)` | Register all colony types (including Inventory) for snapshot/restore |
| `NeedHelper.add/get_value/set_value/is_critical` | Need manipulation |
| `effective(stat_block, modifiers, name)` | Get base + modifier total |
| `add_modifier(mods, stat, amount, duration)` | Add a temporary modifier |
| `add_to_container/remove_from_container/transfer/contents/parent_of` | Containment helpers |

## ColonySnapshot

Unified snapshot/restore that coordinates engine state with colony-specific objects:

```python
from tick_colony import ColonySnapshot, Grid2D, EventLog, CellMap, CellDef

grid = Grid2D(20, 20)
event_log = EventLog()
cells = CellMap(default=CellDef(name="grass"))

snapper = ColonySnapshot(grid=grid, event_log=event_log, cellmap=cells)

# Snapshot
data = snapper.snapshot(engine)

# Restore (into new engine with fresh objects)
snapper2 = ColonySnapshot(grid=grid2, event_log=event_log2, cellmap=cells2)
snapper2.restore(engine2, data)
```

All 6 parameters are optional. Snapshots taken before v0.3.0 (without cellmap/ability_manager/resource_registry keys) restore safely.

## Part of [tick-engine](../../README.md)

MIT License
