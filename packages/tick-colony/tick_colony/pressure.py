"""Pressure monitor system for LLM re-query triggering.

Detects significant colony state changes and resets LLM agent cooldowns so
the strategic layer can react promptly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Sequence

from tick_colony.needs import NeedHelper, NeedSet
from tick_llm.components import LLMAgent
from tick_resource import Inventory

if TYPE_CHECKING:
    from tick import World
    from tick.types import TickContext
    from tick_colony.events import EventLog


@dataclass
class PressureThresholds:
    """Configurable thresholds for pressure detection."""

    resource_change: float = 0.2
    population_change: float = 0.15
    critical_needs_ratio: float = 0.3
    event_types: Sequence[str] = ()
    event_burst: int = 5
    custom: dict[str, Callable[["World"], float]] = field(default_factory=dict)


def make_pressure_system(
    thresholds: PressureThresholds | None = None,
    event_log: EventLog | None = None,
    *,
    check_interval: int = 5,
    min_priority: int = 0,
    on_pressure: Callable[["World", int, str, float], None] | None = None,
) -> Callable[["World", "TickContext"], None]:
    """Return a system that monitors colony pressure and resets LLM cooldowns.

    Should be added to the engine **before** the LLM system so resets take
    effect in the same tick.
    """
    cfg = thresholds if thresholds is not None else PressureThresholds()

    # Closure state
    prev_resources: dict[str, int] = {}
    prev_population: list[int] = [0]  # mutable wrapper
    last_check_tick: list[int] = [0]

    def _reset_agents(world: World, tick: int, ptype: str, magnitude: float) -> None:
        for _, (agent,) in world.query(LLMAgent):
            if agent.priority >= min_priority:
                agent.cooldown_until = 0
                agent.last_query_tick = 0
        if on_pressure is not None:
            on_pressure(world, tick, ptype, magnitude)

    def _check_resources(world: World) -> tuple[bool, float]:
        totals: dict[str, int] = {}
        for _, (inv,) in world.query(Inventory):
            for k, v in inv.slots.items():
                totals[k] = totals.get(k, 0) + v
        current_sum = sum(totals.values())
        prev_sum = sum(prev_resources.values())
        prev_resources.clear()
        prev_resources.update(totals)
        if prev_sum == 0:
            return False, 0.0
        change = abs(current_sum - prev_sum) / prev_sum
        return change >= cfg.resource_change, change

    def _check_population(world: World) -> tuple[bool, float]:
        count = sum(1 for _ in world.query(NeedSet))
        prev = prev_population[0]
        prev_population[0] = count
        if prev == 0:
            return False, 0.0
        change = abs(count - prev) / prev
        return change >= cfg.population_change, change

    def _check_critical(world: World) -> tuple[bool, float]:
        total = 0
        critical_count = 0
        for _, (ns,) in world.query(NeedSet):
            total += 1
            for name in NeedHelper.names(ns):
                if NeedHelper.is_critical(ns, name):
                    critical_count += 1
                    break
        if total == 0:
            return False, 0.0
        ratio = critical_count / total
        return ratio >= cfg.critical_needs_ratio, ratio

    def _check_events(prev_tick: int) -> tuple[bool, float]:
        if event_log is None or not cfg.event_types:
            return False, 0.0
        type_set = set(cfg.event_types)
        events = event_log.query(after=prev_tick)
        count = sum(1 for e in events if e.type in type_set)
        return count >= cfg.event_burst, float(count)

    def pressure_system(world: World, ctx: TickContext) -> None:
        if ctx.tick_number - last_check_tick[0] < check_interval:
            return
        tick = ctx.tick_number
        prev_tick = last_check_tick[0]
        last_check_tick[0] = tick

        fired, mag = _check_resources(world)
        if fired:
            _reset_agents(world, tick, "resource_change", mag)
            return

        fired, mag = _check_population(world)
        if fired:
            _reset_agents(world, tick, "population_change", mag)
            return

        fired, mag = _check_critical(world)
        if fired:
            _reset_agents(world, tick, "critical_needs", mag)
            return

        fired, mag = _check_events(prev_tick)
        if fired:
            _reset_agents(world, tick, "event_burst", mag)
            return

        for name, fn in cfg.custom.items():
            val = fn(world)
            if val >= 1.0:
                _reset_agents(world, tick, name, val)
                return

    return pressure_system
