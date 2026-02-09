"""Ability definitions and callbacks for player abilities."""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.components import Colonist
from tick_colony import (
    AbilityDef, AbilityManager, AbilityGuards,
    NeedHelper, NeedSet, Modifiers, add_modifier,
    InventoryHelper, Inventory,
)

if TYPE_CHECKING:
    from tick import TickContext, World
    from tick_signal import SignalBus


ABILITY_DEFS = [
    AbilityDef(name="food_drop", duration=0, cooldown=100, max_charges=5),
    AbilityDef(name="rally", duration=40, cooldown=200, max_charges=-1),
    AbilityDef(name="shelter", duration=60, cooldown=300, max_charges=-1),
]

ABILITY_LABELS = {
    "food_drop": "Food Drop",
    "rally": "Rally",
    "shelter": "Shelter",
}

ABILITY_KEYS = {
    "food_drop": "F1",
    "rally": "F2",
    "shelter": "F3",
}


def make_ability_manager() -> AbilityManager:
    """Create and configure the ability manager."""
    mgr = AbilityManager()
    for defn in ABILITY_DEFS:
        mgr.define(defn)
    return mgr


def make_ability_callbacks(bus: SignalBus, stockpile_eid: int):
    """Return (on_start, on_end, on_tick) for the ability system."""

    def on_start(world: World, ctx: TickContext, name: str) -> None:
        bus.publish("ability", text=f"{ABILITY_LABELS.get(name, name)} activated!")
        if name == "food_drop":
            if world.alive(stockpile_eid) and world.has(stockpile_eid, Inventory):
                InventoryHelper.add(world.get(stockpile_eid, Inventory), "food", 10)
                bus.publish("ability", text="Food Drop: +10 food to stockpile")

    def on_end(world: World, ctx: TickContext, name: str) -> None:
        if name == "rally":
            bus.publish("ability", text="Rally ended")
        elif name == "shelter":
            bus.publish("ability", text="Shelter ended")

    def on_tick(world: World, ctx: TickContext, name: str, rem: int) -> None:
        if name == "rally":
            for eid, (col, mods) in world.query(Colonist, Modifiers):
                add_modifier(mods, "speed", 3.0, duration=2)
        elif name == "shelter":
            for eid, (col, ns) in world.query(Colonist, NeedSet):
                NeedHelper.set_value(ns, "hunger",
                                     NeedHelper.get_value(ns, "hunger") + 0.5)
                NeedHelper.set_value(ns, "fatigue",
                                     NeedHelper.get_value(ns, "fatigue") + 0.3)

    return on_start, on_end, on_tick
