"""Callbacks for tween completion, FSM transitions, and timer events."""
from __future__ import annotations

from typing import TYPE_CHECKING

from tick_schedule import Timer
from tick_signal import SignalBus
from tick_tween import Tween

from game.components import AutoWaveTag, OrbState

if TYPE_CHECKING:
    from tick import EntityId, TickContext, World


def make_on_tween_complete(bus: SignalBus):
    """Create a tween on_complete callback that publishes to the signal bus."""

    def on_tween_complete(
        world: World, ctx: TickContext, eid: EntityId, tween: Tween
    ) -> None:
        if world.has(eid, OrbState):
            orb = world.get(eid, OrbState)
            bus.publish("orb_complete", easing=orb.easing, lane=orb.lane)

    return on_tween_complete


def make_on_timer_fire(launch_wave_fn, get_duration):
    """Create a timer on_fire callback that launches waves and re-arms the timer.

    get_duration is a callable returning the current duration setting.
    """

    def on_timer_fire(
        world: World, ctx: TickContext, eid: EntityId, timer: Timer
    ) -> None:
        if timer.name == "auto_wave" and world.has(eid, AutoWaveTag):
            launch_wave_fn()
            # Re-arm with current duration (timer.remaining is 0 after firing)
            world.attach(eid, Timer(name="auto_wave", remaining=get_duration()))

    return on_timer_fire
