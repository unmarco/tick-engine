"""Timer, lifecycle, need, and event callbacks."""
from __future__ import annotations

from typing import TYPE_CHECKING

from game.components import Colonist
from tick_colony import (
    NeedHelper, NeedSet, Modifiers, add_modifier,
    InventoryHelper, Inventory,
)
from tick_schedule import Timer

if TYPE_CHECKING:
    from tick import TickContext, World
    from tick_signal import SignalBus


def make_on_fire(bus: SignalBus):
    """Return the timer fire callback."""
    def on_fire(world: World, ctx: TickContext, eid: int, timer: Timer) -> None:
        if not world.alive(eid):
            return
        ns = world.get(eid, NeedSet)
        nm = world.get(eid, Colonist).name if world.has(eid, Colonist) else str(eid)
        if timer.name == "forage":
            NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") + 30.0)
        elif timer.name == "rest":
            NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") + 40.0)
            if world.has(eid, Modifiers):
                add_modifier(world.get(eid, Modifiers), "strength", 2.0, duration=20)
        elif timer.name == "build":
            bus.publish("build_done", colonist=nm)
    return on_fire


def make_on_zero(bus: SignalBus):
    """Return the need-reaches-zero callback."""
    def on_zero(world: World, ctx: TickContext, eid: int, need: str) -> None:
        if not world.has(eid, Colonist):
            return
        nm = world.get(eid, Colonist).name
        if need == "hunger":
            bus.publish("death", name=nm, cause="starvation")
            world.despawn(eid)
        elif need == "fatigue":
            bus.publish("exhaustion", name=nm)
    return on_zero


def make_on_death(bus: SignalBus):
    """Return the lifecycle on_death callback."""
    def on_death(world: World, ctx: TickContext, eid: int, cause: str) -> None:
        if not world.has(eid, Colonist):
            return
        nm = world.get(eid, Colonist).name
        bus.publish("death", name=nm, cause="old_age")
    return on_death


SEASONS = ("spring", "summer", "autumn", "winter")
W_EVENTS = ("cold_snap", "heat_wave", "bountiful_harvest", "raid", "plague")


def make_event_callbacks(bus: SignalBus, stockpile_eid: int):
    """Return (on_start, on_end, on_tick) for the event system."""

    def on_start(world: World, ctx: TickContext, name: str) -> None:
        if name in SEASONS:
            bus.publish("season", season=name)
        elif name in W_EVENTS:
            bus.publish("event_start", event=name)

        if name == "bountiful_harvest":
            for eid, (ns,) in world.query(NeedSet):
                if world.has(eid, Colonist):
                    NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") + 20)
        elif name == "raid":
            cols = [(e, c) for e, (c,) in world.query(Colonist)]
            if cols:
                for e, c in ctx.random.sample(cols, min(len(cols), ctx.random.randint(2, 4))):
                    ns = world.get(e, NeedSet)
                    NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") - 40)
                    bus.publish("raid_damage", colonist=c.name)
            if world.alive(stockpile_eid) and world.has(stockpile_eid, Inventory):
                inv = world.get(stockpile_eid, Inventory)
                InventoryHelper.remove(inv, "food", ctx.random.randint(3, 10))

    def on_end(world: World, ctx: TickContext, name: str) -> None:
        if name in W_EVENTS:
            bus.publish("event_end", event=name)

    def on_tick(world: World, ctx: TickContext, name: str, rem: int) -> None:
        if name == "cold_snap":
            for eid, (ns,) in world.query(NeedSet):
                if world.has(eid, Colonist):
                    NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") - 1.5)
        elif name == "heat_wave":
            for eid, (ns,) in world.query(NeedSet):
                if world.has(eid, Colonist):
                    NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") - 1.0)
        elif name == "plague":
            for eid, (ns,) in world.query(NeedSet):
                if world.has(eid, Colonist):
                    NeedHelper.set_value(ns, "hunger", NeedHelper.get_value(ns, "hunger") - 0.8)
                    NeedHelper.set_value(ns, "fatigue", NeedHelper.get_value(ns, "fatigue") - 0.8)

    return on_start, on_end, on_tick
