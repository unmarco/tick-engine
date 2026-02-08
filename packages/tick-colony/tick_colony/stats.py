from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from tick import TickContext, World


@dataclass
class StatBlock:
    data: dict[str, float] = field(default_factory=dict)


@dataclass
class Modifiers:
    entries: list[list[Any]] = field(default_factory=list)


def effective(stat_block: StatBlock, modifiers: Modifiers, name: str) -> float:
    base = stat_block.data.get(name, 0.0)
    bonus: float = sum(e[1] for e in modifiers.entries if e[0] == name)
    return base + bonus


def add_modifier(modifiers: Modifiers, stat_name: str, amount: float,
                 duration: int = -1) -> None:
    modifiers.entries.append([stat_name, amount, duration])


def remove_modifiers(modifiers: Modifiers, stat_name: str) -> None:
    modifiers.entries = [e for e in modifiers.entries if e[0] != stat_name]


def make_modifier_tick_system() -> Callable[[World, TickContext], None]:
    def modifier_tick_system(world: World, ctx: TickContext) -> None:
        for eid, (mods,) in world.query(Modifiers):
            for entry in mods.entries:
                if entry[2] > 0:
                    entry[2] -= 1
            mods.entries = [e for e in mods.entries if e[2] != 0]
    return modifier_tick_system
