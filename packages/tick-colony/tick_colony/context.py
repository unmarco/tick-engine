"""Context builder factories for LLM prompt assembly.

Each factory returns a ``ContextFn = Callable[[World, int], str]`` that
formats colony state as plain text for LLM consumption.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Sequence

from tick_ai.components import Blackboard
from tick_colony.needs import NeedHelper, NeedSet
from tick_fsm import FSM
from tick_resource import Inventory

if TYPE_CHECKING:
    from tick import World
    from tick_atlas import CellMap
    from tick_colony.events import EventLog
    from tick_colony.lifecycle import Lifecycle
    from tick_spatial import Grid2D

ContextFn = Callable[["World", int], str]


def make_resource_context(
    resource_names: Sequence[str] | None = None,
    *,
    include_capacities: bool = False,
) -> ContextFn:
    """Return a context function that summarises colony resource state."""

    def _context(world: World, eid: int) -> str:
        totals: dict[str, int] = {}
        stockpiles: list[tuple[int, dict[str, int], int, int]] = []
        for sid, (inv,) in world.query(Inventory):
            slots = inv.slots
            if resource_names is not None:
                slots = {k: v for k, v in slots.items() if k in resource_names}
            for k, v in slots.items():
                totals[k] = totals.get(k, 0) + v
            if slots:
                used = sum(inv.slots.values())
                stockpiles.append((sid, dict(slots), used, inv.capacity))
        if not totals:
            return "=== Resources ===\nNo inventories found."
        lines = ["=== Resources ==="]
        totals_str = ", ".join(f"{k}={v}" for k, v in sorted(totals.items()))
        lines.append(f"Colony totals: {totals_str}")
        lines.append(f"Stockpiles: {len(stockpiles)} entities")
        for sid, slots, used, cap in stockpiles:
            slot_str = ", ".join(f"{k}={v}" for k, v in sorted(slots.items()))
            entry = f"  Entity {sid}: {slot_str}"
            if include_capacities and cap >= 0:
                entry += f" (capacity: {used}/{cap})"
            lines.append(entry)
        return "\n".join(lines)

    return _context


def make_population_context(
    *,
    include_needs: bool = True,
    include_fsm_states: bool = True,
    include_lifecycle: bool = False,
) -> ContextFn:
    """Return a context function that summarises colony population."""

    def _context(world: World, eid: int) -> str:
        lines = ["=== Population ==="]

        # Count entities with NeedSet as population proxy
        need_entities = list(world.query(NeedSet))
        total = len(need_entities)
        lines.append(f"Total entities: {total}")

        if include_fsm_states:
            state_counts: dict[str, int] = {}
            for _, (fsm,) in world.query(FSM):
                state_counts[fsm.state] = state_counts.get(fsm.state, 0) + 1
            if state_counts:
                states_str = ", ".join(
                    f"{k}={v}" for k, v in sorted(state_counts.items())
                )
                lines.append(f"FSM states: {states_str}")

        if include_needs and need_entities:
            sums: dict[str, float] = {}
            counts: dict[str, int] = {}
            critical: dict[str, int] = {}
            for _, (ns,) in need_entities:
                for name in NeedHelper.names(ns):
                    val = NeedHelper.get_value(ns, name)
                    sums[name] = sums.get(name, 0.0) + val
                    counts[name] = counts.get(name, 0) + 1
                    if NeedHelper.is_critical(ns, name):
                        critical[name] = critical.get(name, 0) + 1
            if sums:
                avg_parts = []
                for name in sorted(sums):
                    avg_parts.append(f"{name}={sums[name] / counts[name]:.1f}")
                lines.append(f"Need levels (avg): {', '.join(avg_parts)}")
            if any(v > 0 for v in critical.values()):
                crit_parts = [
                    f"{v} {k}" for k, v in sorted(critical.items()) if v > 0
                ]
                lines.append(f"Critical: {', '.join(crit_parts)}")

        if include_lifecycle:
            from tick_colony.lifecycle import Lifecycle as _Lifecycle

            ages: list[int] = []
            for _, (lc,) in world.query(_Lifecycle):
                if lc.max_age > 0:
                    ages.append(lc.max_age)
            if ages:
                lines.append(
                    f"Lifecycle: {len(ages)} mortal, "
                    f"avg max_age={sum(ages) / len(ages):.0f}"
                )

        return "\n".join(lines)

    return _context


def make_spatial_context(
    grid: Grid2D,
    cellmap: CellMap | None = None,
    *,
    radius: int = -1,
) -> ContextFn:
    """Return a context function that describes the entity's spatial surroundings."""

    def _context(world: World, eid: int) -> str:
        lines = ["=== Spatial ==="]
        pos = grid.position_of(eid)
        if pos is None:
            lines.append("Position: unknown")
            return "\n".join(lines)
        lines.append(f"Position: {pos}")

        if radius < 0:
            nearby = grid.tracked_entities()
            nearby_list = [(e, grid.position_of(e)) for e in nearby if e != eid]
        else:
            results = grid.in_radius(pos, radius)
            nearby_list = [(e, c) for e, c in results if e != eid]

        lines.append(f"Nearby: {len(nearby_list)} entities")
        # Group by coord
        coord_groups: dict[tuple[int, ...], list[int]] = {}
        for e, c in nearby_list:
            if c is not None:
                coord_groups.setdefault(c, []).append(e)
        for coord in sorted(coord_groups):
            eids = coord_groups[coord]
            entry = f"  {coord}: {len(eids)} entit{'y' if len(eids) == 1 else 'ies'}"
            if cellmap is not None:
                cell = cellmap.at(coord)
                entry += f" — {cell.name}"
            lines.append(entry)
        return "\n".join(lines)

    return _context


def make_event_context(
    event_log: EventLog,
    *,
    max_events: int = 20,
    event_types: Sequence[str] | None = None,
) -> ContextFn:
    """Return a context function that lists recent events."""

    def _context(world: World, eid: int) -> str:
        events = event_log.query()
        if event_types is not None:
            type_set = set(event_types)
            events = [e for e in events if e.type in type_set]
        events = events[-max_events:]
        lines = ["=== Recent Events ==="]
        if not events:
            lines.append("  No recent events.")
        for ev in events:
            data_str = ", ".join(f"{k}={v}" for k, v in sorted(ev.data.items()))
            lines.append(f"  [Tick {ev.tick}] {ev.type}: {data_str}")
        return "\n".join(lines)

    return _context


def make_colony_context(
    grid: Grid2D | None = None,
    cellmap: CellMap | None = None,
    event_log: EventLog | None = None,
    *,
    resource_names: Sequence[str] | None = None,
    max_events: int = 10,
    spatial_radius: int = -1,
    include_strategy: bool = True,
) -> ContextFn:
    """Return a combined context function using all available colony data."""
    builders: list[ContextFn] = []
    builders.append(make_resource_context(resource_names))
    builders.append(make_population_context())
    if grid is not None:
        builders.append(make_spatial_context(grid, cellmap, radius=spatial_radius))
    if event_log is not None:
        builders.append(make_event_context(event_log, max_events=max_events))

    def _context(world: World, eid: int) -> str:
        sections = [b(world, eid) for b in builders]
        if include_strategy and world.has(eid, Blackboard):
            bb = world.get(eid, Blackboard)
            strategy = bb.data.get("strategy")
            if strategy:
                sections.append(f"=== Current Strategy ===\n{strategy}")
        return "\n\n".join(sections)

    return _context
