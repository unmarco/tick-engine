from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from tick import EntityId, TickContext, World


@dataclass
class NeedSet:
    data: dict[str, list[float]] = field(default_factory=dict)


class NeedHelper:
    @staticmethod
    def add(need_set: NeedSet, name: str, value: float, max_val: float,
            decay_rate: float, critical_threshold: float) -> None:
        need_set.data[name] = [value, max_val, decay_rate, critical_threshold]

    @staticmethod
    def get_value(need_set: NeedSet, name: str) -> float:
        return need_set.data[name][0]

    @staticmethod
    def set_value(need_set: NeedSet, name: str, value: float) -> None:
        entry = need_set.data[name]
        entry[0] = max(0.0, min(value, entry[1]))

    @staticmethod
    def is_critical(need_set: NeedSet, name: str) -> bool:
        entry = need_set.data[name]
        return entry[0] <= entry[3]

    @staticmethod
    def names(need_set: NeedSet) -> list[str]:
        return list(need_set.data.keys())


def make_need_decay_system(
    on_critical: Callable[[World, TickContext, int, str], None] | None = None,
    on_zero: Callable[[World, TickContext, int, str], None] | None = None,
) -> Callable:
    def need_decay_system(world: World, ctx: TickContext) -> None:
        for eid, (ns,) in list(world.query(NeedSet)):
            for name, entry in ns.data.items():
                was_above_critical = entry[0] > entry[3]
                was_above_zero = entry[0] > 0.0
                entry[0] = max(0.0, entry[0] - entry[2])
                if on_critical and was_above_critical and entry[0] <= entry[3]:
                    on_critical(world, ctx, eid, name)
                if on_zero and was_above_zero and entry[0] <= 0.0:
                    on_zero(world, ctx, eid, name)
                    break
    return need_decay_system
